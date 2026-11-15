from decimal import Decimal
from django.utils import timezone
from apps.menu.models import Category, Dish
from .models import RestaurantSEOProfile, PageSEOMetadata


def get_restaurant_schema_jsonld() -> dict:
    """
    Generates Schema.org/Restaurant JSON-LD matching Google Rich Snippet Guidelines.
    Used by search engines to display rich cards, star ratings, opening hours, and menus.
    """
    profile = RestaurantSEOProfile.get_profile()
    domain = profile.canonical_domain.rstrip('/')

    opening_hours_specs = []
    # Convert weekly opening hours to Schema.org OpeningHoursSpecification
    # e.g. Monday-Sunday shifts
    opening_hours_specs.append({
        "@type": "OpeningHoursSpecification",
        "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday"],
        "opens": "12:00",
        "closes": "23:00"
    })
    opening_hours_specs.append({
        "@type": "OpeningHoursSpecification",
        "dayOfWeek": ["Friday", "Saturday"],
        "opens": "12:00",
        "closes": "23:30"
    })
    opening_hours_specs.append({
        "@type": "OpeningHoursSpecification",
        "dayOfWeek": ["Sunday"],
        "opens": "12:00",
        "closes": "22:30"
    })

    schema = {
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "@id": f"{domain}/#restaurant",
        "name": profile.restaurant_name,
        "description": profile.meta_description_default,
        "url": domain,
        "telephone": profile.phone,
        "email": profile.email,
        "priceRange": profile.price_range,
        "servesCuisine": profile.cuisine_types or ["Indian", "Curry", "Tandoori", "Biryani"],
        "menu": f"{domain}/menu",
        "acceptsReservations": "True",
        "image": [
            profile.og_image_url or f"{domain}/static/images/restaurant-exterior.jpg"
        ],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": profile.street_address,
            "addressLocality": profile.city,
            "addressRegion": profile.region,
            "postalCode": profile.postal_code,
            "addressCountry": profile.country
        },
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": float(profile.latitude),
            "longitude": float(profile.longitude)
        },
        "hasMap": profile.google_maps_embed_url or f"https://www.google.com/maps/search/?api=1&query={profile.latitude},{profile.longitude}",
        "openingHoursSpecification": opening_hours_specs,
        "potentialAction": [
            {
                "@type": "ReserveAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": f"{domain}/reservations",
                    "inLanguage": "en-IE",
                    "actionPlatform": [
                        "http://schema.org/DesktopWebPlatform",
                        "http://schema.org/MobileWebPlatform"
                    ]
                },
                "result": {
                    "@type": "FoodEstablishmentReservation",
                    "name": "Table Reservation"
                }
            },
            {
                "@type": "OrderAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": f"{domain}/order",
                    "inLanguage": "en-IE",
                    "actionPlatform": [
                        "http://schema.org/DesktopWebPlatform",
                        "http://schema.org/MobileWebPlatform"
                    ]
                }
            }
        ]
    }
    return schema


def get_menu_schema_jsonld() -> dict:
    """
    Generates Schema.org/Menu with MenuSection and MenuItem objects for Google Search.
    """
    profile = RestaurantSEOProfile.get_profile()
    domain = profile.canonical_domain.rstrip('/')

    categories = Category.objects.prefetch_related('dishes').all()
    sections = []

    for cat in categories:
        dishes = cat.dishes.filter(is_available=True)
        menu_items = []
        for d in dishes:
            menu_items.append({
                "@type": "MenuItem",
                "name": d.name,
                "description": d.description or f"Authentic {d.name} prepared fresh with traditional spices.",
                "image": d.image_url or f"{domain}/static/images/dish-placeholder.jpg",
                "offers": {
                    "@type": "Offer",
                    "price": f"{d.price:.2f}",
                    "priceCurrency": "EUR",
                    "availability": "https://schema.org/InStock"
                }
            })

        sections.append({
            "@type": "MenuSection",
            "name": cat.name,
            "hasMenuItem": menu_items
        })

    schema = {
        "@context": "https://schema.org",
        "@type": "Menu",
        "@id": f"{domain}/menu#menu",
        "name": f"{profile.restaurant_name} A La Carte Menu",
        "url": f"{domain}/menu",
        "inLanguage": "en-IE",
        "hasMenuSection": sections
    }
    return schema


def generate_sitemap_xml(domain_override: str = None) -> str:
    """
    Generates dynamic XML Sitemap compliant with sitemaps.org standards.
    Indexes core site pages, category clean URLs, and dish clean URLs with lastmod & priority.
    """
    profile = RestaurantSEOProfile.get_profile()
    base = (domain_override or profile.canonical_domain).rstrip('/')
    now_date = timezone.now().strftime('%Y-%m-%d')

    url_entries = []

    # 1. Configured core pages
    pages = PageSEOMetadata.objects.filter(is_active=True).order_by('-sitemap_priority')
    for p in pages:
        loc = f"{base}/{p.page_path.lstrip('/')}"
        lastmod = p.updated_at.strftime('%Y-%m-%d') if p.updated_at else now_date
        url_entries.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{p.sitemap_changefreq}</changefreq>\n"
            f"    <priority>{p.sitemap_priority:.1f}</priority>\n"
            f"  </url>"
        )

    # 2. Dynamic Menu Categories
    for cat in Category.objects.all():
        loc = f"{base}/menu/{cat.slug}"
        url_entries.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{now_date}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n"
            f"    <priority>0.8</priority>\n"
            f"  </url>"
        )

    # 3. Dynamic Individual Dishes (Clean URLs)
    for d in Dish.objects.filter(is_available=True).select_related('category'):
        cat_slug = d.category.slug if d.category else 'general'
        loc = f"{base}/menu/{cat_slug}/{d.slug}"
        url_entries.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{now_date}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n"
            f"    <priority>0.7</priority>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(url_entries) + "\n"
        '</urlset>'
    )
    return xml


def generate_robots_txt(domain_override: str = None) -> str:
    """
    Generates standard robots.txt directing search bots to sitemap.xml.
    """
    profile = RestaurantSEOProfile.get_profile()
    base = (domain_override or profile.canonical_domain).rstrip('/')

    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /api/\n"
        "Disallow: /checkout/\n"
        "\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )


def get_local_seo_bundle() -> dict:
    """
    Provides Local SEO & Google Business Profile data bundle for Google Maps embed and NAP display.
    """
    profile = RestaurantSEOProfile.get_profile()
    domain = profile.canonical_domain.rstrip('/')

    directions_url = f"https://www.google.com/maps/dir/?api=1&destination={profile.latitude},{profile.longitude}"

    return {
        'restaurantName': profile.restaurant_name,
        'tagline': profile.tagline,
        'nap': {
            'name': profile.restaurant_name,
            'address': f"{profile.street_address}, {profile.city}, {profile.postal_code}, {profile.country}",
            'streetAddress': profile.street_address,
            'city': profile.city,
            'region': profile.region,
            'postalCode': profile.postal_code,
            'country': profile.country,
            'phone': profile.phone,
            'email': profile.email,
        },
        'geo': {
            'latitude': float(profile.latitude),
            'longitude': float(profile.longitude),
        },
        'googleMaps': {
            'placeId': profile.google_maps_place_id,
            'embedUrl': profile.google_maps_embed_url,
            'businessProfileUrl': profile.google_business_url,
            'directionsUrl': directions_url,
        },
        'openingHours': profile.opening_hours_json,
        'priceRange': profile.price_range,
        'cuisines': profile.cuisine_types,
        'schemaJsonLd': get_restaurant_schema_jsonld(),
    }


def get_page_seo_bundle(path_or_identifier: str = 'home') -> dict:
    """
    Resolves complete SEO metadata, OpenGraph tags, Twitter cards, and Schema.org
    for any frontend page path.
    """
    profile = RestaurantSEOProfile.get_profile()
    domain = profile.canonical_domain.rstrip('/')

    # Look up by identifier or path
    page = PageSEOMetadata.objects.filter(
        models_q_filter(path_or_identifier)
    ).first()

    if page:
        meta_title = page.meta_title
        meta_desc = page.meta_description
        canonical = page.canonical_url or f"{domain}/{page.page_path.lstrip('/')}"
        og_title = page.og_title or meta_title
        og_desc = page.og_description or meta_desc
        og_img = page.og_image or profile.og_image_url
        og_type = page.og_type
        twitter_card = page.twitter_card
        robots = page.robots_directive
    else:
        meta_title = profile.meta_title_default
        meta_desc = profile.meta_description_default
        canonical = f"{domain}/{path_or_identifier.lstrip('/')}"
        og_title = meta_title
        og_desc = meta_desc
        og_img = profile.og_image_url
        og_type = "website"
        twitter_card = "summary_large_image"
        robots = "index, follow"

    # Schema JSON-LD selection
    if 'menu' in path_or_identifier.lower():
        schema_data = get_menu_schema_jsonld()
    else:
        schema_data = get_restaurant_schema_jsonld()

    return {
        'metaTitle': meta_title,
        'metaDescription': meta_desc,
        'canonicalUrl': canonical,
        'robotsDirective': robots,
        'openGraph': {
            'title': og_title,
            'description': og_desc,
            'image': og_img,
            'url': canonical,
            'type': og_type,
            'siteName': profile.restaurant_name,
        },
        'twitter': {
            'card': twitter_card,
            'title': og_title,
            'description': og_desc,
            'image': og_img,
            'site': profile.twitter_handle,
        },
        'analytics': {
            'ga4MeasurementId': profile.ga4_measurement_id,
            'gtmContainerId': profile.gtm_container_id,
            'metaPixelId': profile.meta_pixel_id,
        },
        'schemaJsonLd': schema_data,
    }


def models_q_filter(val: str):
    from django.db.models import Q
    clean_path = f"/{val.strip('/')}"
    return Q(page_identifier=val) | Q(page_path=val) | Q(page_path=clean_path)

