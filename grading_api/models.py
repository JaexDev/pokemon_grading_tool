from django.db import models

# Create your models here.

class PokemonCard(models.Model):
    card_name = models.CharField(max_length=255)
    set_name = models.CharField(max_length=255)
    language = models.CharField(max_length=20, default='English')
    rarity = models.CharField(max_length=100, default = "Unknown")
    tcgplayer_price = models.FloatField(null=True, blank=True)
    psa_10_price = models.FloatField(null=True, blank=True)
    price_delta = models.FloatField(null=True, blank=True)
    profit_potential = models.FloatField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.card_name} ({self.set_name}) - {self.rarity}"