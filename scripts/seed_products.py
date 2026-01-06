"""
Script to seed the database with sample products.
Run this script to populate the database with test data.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database.connection import get_session_factory, init_database, create_engine_instance
from src.database.services.product_service import ProductService
from src.database.services.variation_service import VariationService
from src.database.models.enums import DeliveryType


def seed_products():
    """Seed database with sample products."""
    # Initialize database
    engine = create_engine_instance()
    init_database(engine)
    
    # Get session
    session_factory = get_session_factory(engine)
    session = session_factory()
    
    try:
        product_service = ProductService(session)
        variation_service = VariationService(session)
        
        # Sample products from TO-plan.md
        products_data = [
            {
                "id": "alight_motion",
                "name": "ALIGHT MOTION",
                "description": "Professional video editing app with premium features and effects",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "variations": [
                    {"id": "alight_12m_1", "name": "Pro 12M 1PCS", "price": 40000, "stock": 51},
                    {"id": "alight_12m_50", "name": "Pro 12m 50PCS", "price": 50000, "stock": 981},
                    {"id": "alight_12m_100", "name": "Pro 12m 100PCS", "price": 75000, "stock": 972},
                ]
            },
            {
                "id": "apple_music",
                "name": "APPLE MUSIC",
                "description": "Apple Music subscription with premium features",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "variations": [
                    {"id": "apple_1m", "name": "1 Month", "price": 50000, "stock": 200},
                    {"id": "apple_3m", "name": "3 Months", "price": 120000, "stock": 150},
                    {"id": "apple_12m", "name": "12 Months", "price": 400000, "stock": 100},
                ]
            },
            {
                "id": "canva_lifetime",
                "name": "CANVA LIFETIME",
                "description": "Canva Pro lifetime subscription with all premium features",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "variations": [
                    {"id": "canva_lifetime_1", "name": "Lifetime 1 Account", "price": 200000, "stock": 50},
                ]
            },
            {
                "id": "canva_pro",
                "name": "CANVA PRO",
                "description": "Canva Pro subscription with premium templates and features",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "variations": [
                    {"id": "canva_pro_1m", "name": "1 Month", "price": 30000, "stock": 300},
                    {"id": "canva_pro_12m", "name": "12 Months", "price": 300000, "stock": 200},
                ]
            },
            {
                "id": "capcut_basic",
                "name": "CAPCUT BASIC",
                "description": "CapCut video editing app basic version",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "variations": [
                    {"id": "capcut_basic_1", "name": "Basic 1 Account", "price": 25000, "stock": 500},
                ]
            },
            {
                "id": "capcut_famhead",
                "name": "CAPCUT FAMHEAD",
                "description": "CapCut family head account",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "variations": [
                    {"id": "capcut_famhead_1", "name": "Family Head 1 Account", "price": 35000, "stock": 400},
                ]
            },
            {
                "id": "capcut_pro",
                "name": "CAPCUT PRO",
                "description": "CapCut Pro with advanced editing features",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "variations": [
                    {"id": "capcut_pro_1", "name": "Pro 1 Account", "price": 45000, "stock": 350},
                    {"id": "capcut_pro_12m", "name": "Pro 12 Months", "price": 400000, "stock": 250},
                ]
            },
            {
                "id": "capcut_pro_po",
                "name": "CAPCUT PRO PO",
                "description": "CapCut Pro PO version",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "variations": [
                    {"id": "capcut_pro_po_1", "name": "Pro PO 1 Account", "price": 50000, "stock": 300},
                ]
            },
            {
                "id": "chatgpt_jaspay",
                "name": "CHATGPT JASPAY",
                "description": "ChatGPT subscription via Jaspay",
                "delivery_type": DeliveryType.SUPPLIER_BASED,
                "variations": [
                    {"id": "chatgpt_jaspay_1m", "name": "1 Month", "price": 100000, "stock": 100},
                    {"id": "chatgpt_jaspay_3m", "name": "3 Months", "price": 250000, "stock": 80},
                ]
            },
            {
                "id": "chatgpt_private",
                "name": "CHATGPT PRIVATE",
                "description": "ChatGPT private account",
                "delivery_type": DeliveryType.SUPPLIER_BASED,
                "variations": [
                    {"id": "chatgpt_private_1", "name": "Private 1 Account", "price": 150000, "stock": 60},
                ]
            },
            {
                "id": "chatgpt_sharing",
                "name": "CHATGPT SHARING",
                "description": "ChatGPT shared account",
                "delivery_type": DeliveryType.SUPPLIER_BASED,
                "variations": [
                    {"id": "chatgpt_sharing_1", "name": "Sharing 1 Account", "price": 80000, "stock": 150},
                ]
            },
            {
                "id": "duolingo",
                "name": "DUOLINGO",
                "description": "Duolingo Plus subscription for language learning",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "variations": [
                    {"id": "duolingo_1m", "name": "1 Month", "price": 40000, "stock": 200},
                    {"id": "duolingo_12m", "name": "12 Months", "price": 350000, "stock": 150},
                ]
            },
            {
                "id": "gsuitex_gopay",
                "name": "GSUITEXGOPAY",
                "description": "Google Workspace subscription via GoPay",
                "delivery_type": DeliveryType.SUPPLIER_BASED,
                "variations": [
                    {"id": "gsuitex_gopay_1", "name": "1 Account", "price": 200000, "stock": 50},
                ]
            },
            {
                "id": "gsuitex_psc",
                "name": "GSUITEXPSC",
                "description": "Google Workspace subscription via PSC",
                "delivery_type": DeliveryType.SUPPLIER_BASED,
                "variations": [
                    {"id": "gsuitex_psc_1", "name": "1 Account", "price": 200000, "stock": 50},
                ]
            },
            {
                "id": "google_drive",
                "name": "GOOGLE DRIVE",
                "description": "Google Drive storage subscription",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "variations": [
                    {"id": "gdrive_100gb", "name": "100GB", "price": 50000, "stock": 300},
                    {"id": "gdrive_2tb", "name": "2TB", "price": 300000, "stock": 200},
                ]
            },
        ]
        
        print("🌱 Seeding database with sample products...")
        print(f"Creating {len(products_data)} products...\n")
        
        created_count = 0
        variation_count = 0
        
        for product_data in products_data:
            variations = product_data.pop("variations")
            
            # Check if product already exists
            existing = product_service.get_product_by_id(product_data["id"])
            if existing:
                print(f"⏭️  Product '{product_data['name']}' already exists, skipping...")
                continue
            
            # Create product
            product = product_service.create_product(product_data)
            created_count += 1
            print(f"✅ Created product: {product.name}")
            
            # Create variations
            for var_data in variations:
                var_data["product_id"] = product.id
                var_data["is_active"] = True
                variation = variation_service.create_variation(var_data)
                variation_count += 1
                print(f"   └─ Variation: {variation.name} - {variation.price:,} VND (Stock: {variation.stock})")
        
        print("\n✨ Seeding complete!")
        print(f"   Products created: {created_count}")
        print(f"   Variations created: {variation_count}")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    seed_products()

