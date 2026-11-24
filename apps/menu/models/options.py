from django.db import models

from .dish import Dish


class DishPortionOption(models.Model):
    dish = models.ForeignKey(Dish, related_name='portion_options', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    serving_info = models.CharField(max_length=80, blank=True)
    price_delta = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    inventory_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)

    def __str__(self):
        return f"{self.dish.name} - {self.name} (+€{self.price_delta})"


class DishExtraOption(models.Model):
    dish = models.ForeignKey(Dish, related_name='extra_options', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.dish.name} - {self.name} (${self.price})"
