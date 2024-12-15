from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import PokemonCard
from .serializers import PokemonCardSerializer
from . import scraper
from django.utils import timezone
import logging
from django_filters import rest_framework as filters
import asyncio
import concurrent.futures

logger = logging.getLogger(__name__)

class PokemonCardFilter(filters.FilterSet):
    card_name = filters.CharFilter(field_name='card_name', lookup_expr='icontains')
    set_name = filters.CharFilter(field_name='set_name', lookup_expr='exact')
    tcgplayer_price_min = filters.NumberFilter(field_name='tcgplayer_price', lookup_expr='gte')
    tcgplayer_price_max = filters.NumberFilter(field_name='tcgplayer_price', lookup_expr='lte')
    psa_10_price_min = filters.NumberFilter(field_name='psa_10_price', lookup_expr='gte')
    psa_10_price_max = filters.NumberFilter(field_name='psa_10_price', lookup_expr='lte')

class PokemonCardViewSet(viewsets.ModelViewSet):
    queryset = PokemonCard.objects.all()
    serializer_class = PokemonCardSerializer
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = PokemonCardFilter

    @action(detail=False, methods=['get'])
    def scrape_and_save(self, request):
        search_query = request.query_params.get('searchQuery')
        language = request.query_params.get('language', 'English')

        if not search_query:
            return Response({'error': 'Please provide a card or set name in query params'}, status=400)

        try:
            cards_to_fetch = [{'name': search_query, 'set': search_query, 'language': language}]
            
            logger.info(f"Fetching TCGPlayer data for {search_query} ({language})...")
            tcgplayer_results = scraper.fetch_all_data_concurrent(cards_to_fetch)

            if not tcgplayer_results:
                logger.error(f"Could not get TCGPlayer data for {search_query} ({language}).")
                return Response({'error': 'Could not get TCGPlayer data'}, status=404)

            logger.info("Fetching eBay prices asynchronously...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ebay_prices = loop.run_until_complete(scraper.get_ebay_prices_async(tcgplayer_results))
            loop.close()

            all_cards = []
            for card_data, ebay_price in zip(tcgplayer_results, ebay_prices):
                if ebay_price:
                    logger.info(f"Calculating profits for {card_data.get('card_name')}")
                    profit_data = scraper.calculate_profit([card_data], ebay_price)
                    
                    if profit_data:
                        for card in profit_data:
                            logger.info(f"Creating or updating record for {card.get('card_name')}")
                            card_record, created = PokemonCard.objects.update_or_create(
                                card_name=card.get("card_name"),
                                set_name=card.get("set_name"),
                                language=card.get("language"),
                                rarity=card.get("rarity"),
                                defaults={
                                    'tcgplayer_price': card.get("tcgplayer_price"),
                                    'psa_10_price': card.get("psa_10_price"),
                                    'price_delta': card.get("price_delta"),
                                    'profit_potential': card.get("profit_potential"),
                                    'last_updated': timezone.now()
                                }
                            )
                            all_cards.append(card_record)
                    else:
                        logger.error(f"Could not calculate profits for {card_data.get('card_name')}")
                        continue
                else:
                    logger.error(f"Could not get eBay data for {card_data.get('card_name')}")
                    continue

            if not all_cards:
                return Response({'error': 'No valid cards found'}, status=404)

            serializer = PokemonCardSerializer(all_cards, many=True)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return Response({'error': f'An unexpected error occurred: {e}'}, status=500)

        finally:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.close()
            except:
                pass