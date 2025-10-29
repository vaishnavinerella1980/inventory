
"""
DigiAssets - Complete Digital Inventory Management System with Fixed SQLAlchemy Relationships
Requirements: pip install fastapi uvicorn sqlalchemy psycopg2-binary python-multipart
Run with: python digiassets.py
"""

from fastapi import FastAPI, HTTPException, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text, func, inspect, Numeric, DECIMAL, MetaData, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime, timedelta
from typing import Optional, List
import hashlib
import os
import urllib.parse
from pathlib import Path
import json
from decimal import Decimal
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
password = urllib.parse.quote_plus("postgres")
DATABASE_URL = f"postgresql://postgres:vaishnavi2025@localhost/digiassets"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ============================
# DATABASE MODELS
# ============================

class Division(Base):
    __tablename__ = "divisions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    departments = relationship("Department", back_populates="division")

class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    division_id = Column(Integer, ForeignKey("divisions.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    division = relationship("Division", back_populates="departments")
    users = relationship("User", back_populates="department")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, unique=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    department_id = Column(Integer, ForeignKey("departments.id"))
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    department = relationship("Department", back_populates="users")
    inventory_transactions = relationship("InventoryTransaction", back_populates="user", foreign_keys="InventoryTransaction.user_id")
    confirmed_transactions = relationship("InventoryTransaction", foreign_keys="InventoryTransaction.confirmed_by", overlaps="confirmer")
    orders = relationship("Order", back_populates="created_by_user")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    parent = relationship("Category", remote_side=[id], back_populates="children")
    children = relationship("Category", back_populates="parent")
    items = relationship("ItemMaster", back_populates="category")
    creator = relationship("User")

class ItemMaster(Base):
    __tablename__ = "item_master"
    
    id = Column(Integer, primary_key=True, index=True)
    item_code = Column(String, unique=True, index=True)
    item_name = Column(String, index=True)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey("categories.id"))
    unit_of_measure = Column(String)
    min_stock_level = Column(DECIMAL(15, 3), default=0)
    max_stock_level = Column(DECIMAL(15, 3), default=0)
    standard_cost = Column(DECIMAL(15, 2), default=0)
    location = Column(String)
    barcode = Column(String, unique=True, nullable=True)
    manufacturer = Column(String)
    model_number = Column(String)
    specifications = Column(Text)
    warranty_months = Column(Integer, default=0)
    is_returnable = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"))
    
    category = relationship("Category", back_populates="items")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    inventory_items = relationship("InventoryItem", back_populates="item_master")
    inventory_transactions = relationship("InventoryTransaction", back_populates="item_master")
    order_items = relationship("OrderItem", back_populates="item_master")

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    
    id = Column(Integer, primary_key=True, index=True)
    item_master_id = Column(Integer, ForeignKey("item_master.id"))
    current_quantity = Column(DECIMAL(15, 3), default=0)
    reserved_quantity = Column(DECIMAL(15, 3), default=0)
    returnable_quantity = Column(DECIMAL(15, 3), default=0)
    available_quantity = Column(DECIMAL(15, 3), default=0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    item_master = relationship("ItemMaster", back_populates="inventory_items")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, unique=True, index=True)
    customer_name = Column(String)
    customer_contact = Column(String)
    order_date = Column(DateTime, default=datetime.utcnow)
    expected_delivery_date = Column(DateTime, nullable=True)
    order_status = Column(String, default='PENDING')
    total_amount = Column(DECIMAL(15, 2), default=0)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    created_by_user = relationship("User", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order")
    inventory_transactions = relationship("InventoryTransaction", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    item_master_id = Column(Integer, ForeignKey("item_master.id"))
    requested_quantity = Column(DECIMAL(15, 3))
    fulfilled_quantity = Column(DECIMAL(15, 3), default=0)
    returnable_quantity = Column(DECIMAL(15, 3), default=0)
    unit_price = Column(DECIMAL(15, 2))
    total_price = Column(DECIMAL(15, 2))
    status = Column(String, default='PENDING')
    
    order = relationship("Order", back_populates="order_items")
    item_master = relationship("ItemMaster", back_populates="order_items")

class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_number = Column(String, unique=True, index=True)
    item_master_id = Column(Integer, ForeignKey("item_master.id"))
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    transaction_type = Column(String)
    transaction_sub_type = Column(String)
    quantity = Column(DECIMAL(15, 3))
    returnable_quantity = Column(DECIMAL(15, 3), default=0)
    unit_cost = Column(DECIMAL(15, 2), default=0)
    total_cost = Column(DECIMAL(15, 2), default=0)
    reference_number = Column(String)
    vendor_customer = Column(String)
    remarks = Column(Text)
    transaction_date = Column(DateTime, default=datetime.utcnow)
    expected_return_date = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default='PENDING')
    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    item_master = relationship("ItemMaster", back_populates="inventory_transactions")
    order = relationship("Order", back_populates="inventory_transactions")
    user = relationship("User", foreign_keys=[user_id], back_populates="inventory_transactions")
    confirmer = relationship("User", foreign_keys=[confirmed_by], overlaps="confirmed_transactions")

# ============================
# DATABASE VALIDATION FUNCTIONS
# ============================

def validate_and_migrate_database():
    """
    Comprehensive database schema validation and migration.
    """
    logger.info("🔍 Starting database schema validation...")
    
    try:
        # Get database inspector
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        # Define expected tables and their required columns
        expected_schema = {
            'divisions': [
                'id', 'name', 'description', 'is_default', 'created_at'
            ],
            'departments': [
                'id', 'name', 'description', 'division_id', 'created_at'
            ],
            'users': [
                'id', 'employee_id', 'name', 'email', 'password_hash', 
                'department_id', 'is_admin', 'is_active', 'created_at'
            ],
            'categories': [
                'id', 'name', 'description', 'parent_id', 'is_active', 
                'created_at', 'created_by'
            ],
            'item_master': [
                'id', 'item_code', 'item_name', 'description', 'category_id',
                'unit_of_measure', 'min_stock_level', 'max_stock_level',
                'standard_cost', 'location', 'barcode', 'manufacturer',
                'model_number', 'specifications', 'warranty_months',
                'is_returnable', 'is_active', 'created_at', 'created_by',
                'updated_at', 'updated_by'
            ],
            'inventory_items': [
                'id', 'item_master_id', 'current_quantity', 'reserved_quantity',
                'returnable_quantity', 'available_quantity', 'last_updated'
            ],
            'orders': [
                'id', 'order_number', 'customer_name', 'customer_contact',
                'order_date', 'expected_delivery_date', 'order_status',
                'total_amount', 'notes', 'created_by', 'created_at', 'updated_at'
            ],
            'order_items': [
                'id', 'order_id', 'item_master_id', 'requested_quantity',
                'fulfilled_quantity', 'returnable_quantity', 'unit_price',
                'total_price', 'status'
            ],
            'inventory_transactions': [
                'id', 'transaction_number', 'item_master_id', 'order_id',
                'transaction_type', 'transaction_sub_type', 'quantity',
                'returnable_quantity', 'unit_cost', 'total_cost',
                'reference_number', 'vendor_customer', 'remarks',
                'transaction_date', 'expected_return_date', 'user_id',
                'status', 'confirmed_at', 'confirmed_by', 'created_at'
            ]
        }
        
        # Check and create missing tables
        missing_tables = []
        for table_name in expected_schema.keys():
            if table_name not in existing_tables:
                missing_tables.append(table_name)
        
        if missing_tables:
            logger.info(f"📋 Missing tables found: {missing_tables}")
            logger.info("🔧 Creating missing tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Missing tables created successfully")
        else:
            logger.info("✅ All required tables exist")
        
        # Refresh table list after creation
        existing_tables = inspector.get_table_names()
        
        # Check for missing columns in existing tables
        for table_name, expected_columns in expected_schema.items():
            if table_name in existing_tables:
                existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
                missing_columns = [col for col in expected_columns if col not in existing_columns]
                
                if missing_columns:
                    logger.warning(f"⚠️  Missing columns in {table_name}: {missing_columns}")
                    add_missing_columns(table_name, missing_columns)
                else:
                    logger.info(f"✅ All columns exist in {table_name}")
        
        logger.info("🎉 Database schema validation completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database schema validation failed: {e}")
        return False

def add_missing_columns(table_name, missing_columns):
    """Add missing columns to existing tables."""
    try:
        column_definitions = {
            'is_returnable': 'ADD COLUMN is_returnable BOOLEAN DEFAULT FALSE',
            'returnable_quantity': 'ADD COLUMN returnable_quantity DECIMAL(15,3) DEFAULT 0',
            'expected_return_date': 'ADD COLUMN expected_return_date TIMESTAMP',
            'order_id': 'ADD COLUMN order_id INTEGER',
            'confirmed_by': 'ADD COLUMN confirmed_by INTEGER',
            'confirmed_at': 'ADD COLUMN confirmed_at TIMESTAMP',
            'updated_at': 'ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'updated_by': 'ADD COLUMN updated_by INTEGER',
            'parent_id': 'ADD COLUMN parent_id INTEGER',
            'barcode': 'ADD COLUMN barcode VARCHAR',
            'manufacturer': 'ADD COLUMN manufacturer VARCHAR',
            'model_number': 'ADD COLUMN model_number VARCHAR',
            'specifications': 'ADD COLUMN specifications TEXT',
            'warranty_months': 'ADD COLUMN warranty_months INTEGER DEFAULT 0',
            'notes': 'ADD COLUMN notes TEXT',
            'expected_delivery_date': 'ADD COLUMN expected_delivery_date TIMESTAMP',
            'order_status': 'ADD COLUMN order_status VARCHAR DEFAULT \'PENDING\'',
            'total_amount': 'ADD COLUMN total_amount DECIMAL(15,2) DEFAULT 0',
            'customer_contact': 'ADD COLUMN customer_contact VARCHAR',
            'fulfilled_quantity': 'ADD COLUMN fulfilled_quantity DECIMAL(15,3) DEFAULT 0',
            'unit_price': 'ADD COLUMN unit_price DECIMAL(15,2)',
            'total_price': 'ADD COLUMN total_price DECIMAL(15,2)',
            'reserved_quantity': 'ADD COLUMN reserved_quantity DECIMAL(15,3) DEFAULT 0',
            'available_quantity': 'ADD COLUMN available_quantity DECIMAL(15,3) DEFAULT 0',
            'last_updated': 'ADD COLUMN last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        from sqlalchemy import text
        with engine.connect() as conn:
            for column in missing_columns:
                if column in column_definitions:
                    try:
                        sql = f"ALTER TABLE {table_name} {column_definitions[column]}"
                        conn.execute(text(sql))
                        logger.info(f"✅ Added column {column} to {table_name}")
                    except Exception as e:
                        logger.warning(f"⚠️  Could not add column {column} to {table_name}: {e}")
            conn.commit()
            
    except Exception as e:
        logger.error(f"❌ Error adding missing columns to {table_name}: {e}")

def create_database():
    """Enhanced database creation with comprehensive validation"""
    try:
        # Create database if it doesn't exist
        from sqlalchemy import text
        password = urllib.parse.quote_plus("postgres")
        temp_engine = create_engine(f"postgresql://postgres:vaishnavi2025@localhost/postgres")
        
        with temp_engine.connect() as conn:
            conn.execute(text("COMMIT"))
            try:
                conn.execute(text("CREATE DATABASE digiassets"))
                logger.info("✅ Created database: digiassets")
            except Exception as e:
                logger.info(f"ℹ️  Database already exists")
        
        # Validate and migrate database schema
        schema_valid = validate_and_migrate_database()
        
        if not schema_valid:
            logger.error("❌ Database schema validation failed!")
            return False
        
        # Create default data
        create_default_data()
        
        logger.info("🎉 Database initialization completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        return False

def create_default_data():
    """Create default data with enhanced error handling"""
    db = SessionLocal()
    try:
        # Create default division
        existing_division = db.query(Division).filter(Division.is_default == True).first()
        if not existing_division:
            default_division = Division(
                name="Company", 
                description="Default Company Division", 
                is_default=True
            )
            db.add(default_division)
            db.commit()
            db.refresh(default_division)
            logger.info(f"✅ Created default division: {default_division.name}")
        else:
            default_division = existing_division
            logger.info(f"ℹ️  Using existing default division: {default_division.name}")
        
        # Create default department
        existing_dept = db.query(Department).first()
        if not existing_dept:
            admin_dept = Department(
                name="Administration", 
                description="Administrative Department",
                division_id=default_division.id
            )
            db.add(admin_dept)
            db.commit()
            db.refresh(admin_dept)
            logger.info(f"✅ Created department: {admin_dept.name}")
        else:
            admin_dept = existing_dept
            if not admin_dept.division_id:
                admin_dept.division_id = default_division.id
                db.commit()
            logger.info(f"ℹ️  Using existing department: {admin_dept.name}")
        
        # Create default admin user
        existing_admin = db.query(User).filter(User.employee_id == "ADMIN001").first()
        if not existing_admin:
            admin_password = "admin123"
            hashed_password = hash_password(admin_password)
            
            admin_user = User(
                employee_id="ADMIN001",
                name="System Administrator",
                email="admin@company.com",
                password_hash=hashed_password,
                department_id=admin_dept.id,
                is_admin=True
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            logger.info("✅ Created default admin user: ADMIN001 / admin123")
        else:
            admin_user = existing_admin
            logger.info(f"ℹ️  Admin user already exists: {existing_admin.name}")
        
        # Create default categories
        default_categories = [
            {"name": "IT Equipment", "description": "Information Technology Equipment"},
            {"name": "Office Supplies", "description": "General Office Supplies"},
            {"name": "Furniture", "description": "Office Furniture and Fixtures"},
            {"name": "Machinery", "description": "Industrial Machinery and Equipment"},
            {"name": "Vehicles", "description": "Company Vehicles"},
            {"name": "Consumables", "description": "Consumable Items"},
            {"name": "Returnable Items", "description": "Items that can be returned after use"}
        ]
        
        for cat_data in default_categories:
            existing_cat = db.query(Category).filter(Category.name == cat_data["name"]).first()
            if not existing_cat:
                category = Category(
                    name=cat_data["name"],
                    description=cat_data["description"],
                    created_by=admin_user.id
                )
                db.add(category)
                
        db.commit()
        logger.info("✅ Created default categories")
        
        # Create sample items if none exist
        item_count = db.query(ItemMaster).count()
        if item_count == 0:
            create_sample_items(db, admin_user.id)
            
    except Exception as e:
        logger.error(f"❌ Error creating default data: {e}")
        db.rollback()
    finally:
        db.close()

def get_available_stock(item_id: int, db: Session) -> float:
    """Get available stock for an item (current - reserved)"""
    inventory_item = db.query(InventoryItem).filter(InventoryItem.item_master_id == item_id).first()
    if inventory_item:
        return float(inventory_item.current_quantity - inventory_item.reserved_quantity)
    return 0.0

def create_sample_items(db: Session, admin_user_id: int):
    """Create sample items for demonstration"""
    try:
        # Get categories
        it_category = db.query(Category).filter(Category.name == "IT Equipment").first()
        office_category = db.query(Category).filter(Category.name == "Office Supplies").first()
        returnable_category = db.query(Category).filter(Category.name == "Returnable Items").first()
        
        if not it_category or not office_category or not returnable_category:
            logger.warning("⚠️  Required categories not found for sample items")
            return
        
        sample_items = [
            {
                "item_code": "IT001",
                "item_name": "Dell Laptop",
                "description": "Dell Inspiron 15 3000 Series",
                "category_id": it_category.id,
                "unit_of_measure": "PCS",
                "min_stock_level": 5,
                "max_stock_level": 20,
                "standard_cost": 45000,
                "location": "IT Store",
                "manufacturer": "Dell",
                "model_number": "Inspiron 15 3000",
                "warranty_months": 12,
                "is_returnable": True
            },
            {
                "item_code": "OFF001",
                "item_name": "A4 Paper",
                "description": "A4 Size Copier Paper",
                "category_id": office_category.id,
                "unit_of_measure": "BOX",
                "min_stock_level": 10,
                "max_stock_level": 50,
                "standard_cost": 300,
                "location": "Office Store",
                "manufacturer": "JK Paper",
                "model_number": "A4-500",
                "warranty_months": 0,
                "is_returnable": False
            },
            {
                "item_code": "RET001",
                "item_name": "Projector",
                "description": "Portable LCD Projector",
                "category_id": returnable_category.id,
                "unit_of_measure": "PCS",
                "min_stock_level": 2,
                "max_stock_level": 10,
                "standard_cost": 25000,
                "location": "Equipment Room",
                "manufacturer": "Epson",
                "model_number": "EB-S41",
                "warranty_months": 24,
                "is_returnable": True
            }
        ]
        
        for item_data in sample_items:
            existing_item = db.query(ItemMaster).filter(ItemMaster.item_code == item_data["item_code"]).first()
            if not existing_item:
                item = ItemMaster(
                    **item_data,
                    created_by=admin_user_id,
                    updated_by=admin_user_id
                )
                db.add(item)
                db.flush()
                
                # Create inventory item record
                inventory_item = InventoryItem(
                    item_master_id=item.id,
                    current_quantity=0,
                    reserved_quantity=0,
                    returnable_quantity=0,
                    available_quantity=0
                )
                db.add(inventory_item)
        
        db.commit()
        logger.info("✅ Created sample items")
        
    except Exception as e:
        logger.error(f"❌ Error creating sample items: {e}")

# ============================
# FASTAPI APPLICATION SETUP
# ============================

app = FastAPI(title="DigiAssets - Complete Digital Inventory Management System")

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)
os.makedirs("static/images", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# UTILITY FUNCTIONS
# ============================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

# Session management
active_sessions = {}

def cleanup_expired_sessions():
    """Remove sessions older than 24 hours"""
    try:
        expired_sessions = []
        current_time = datetime.utcnow()
        
        for session_id, session_data in active_sessions.items():
            session_age = current_time - session_data["created_at"]
            if session_age.total_seconds() > 86400:  # 24 hours
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del active_sessions[session_id]
            
        if expired_sessions:
            logger.info(f"🧹 Cleaned up {len(expired_sessions)} expired sessions")
    except Exception as e:
        logger.error(f"❌ Error cleaning up sessions: {e}")

def create_session(user_id: int) -> str:
    cleanup_expired_sessions()
    
    session_id = hashlib.sha256(f"{user_id}{datetime.utcnow()}".encode()).hexdigest()
    active_sessions[session_id] = {
        "user_id": user_id,
        "created_at": datetime.utcnow()
    }
    logger.info(f"🔐 Created session for user {user_id}")
    return session_id

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session_data = active_sessions[session_id]
    session_age = datetime.utcnow() - session_data["created_at"]
    if session_age.total_seconds() > 86400:  # 24 hours
        del active_sessions[session_id]
        raise HTTPException(status_code=401, detail="Session expired")
    
    user_id = session_data["user_id"]
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    return user

def generate_transaction_number() -> str:
    """Generate unique transaction number"""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"TXN{timestamp}"

def generate_order_number() -> str:
    """Generate unique order number"""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"ORD{timestamp}"

def get_current_stock(item_id: int, db: Session) -> float:
    """Get current stock for an item"""
    inventory_item = db.query(InventoryItem).filter(InventoryItem.item_master_id == item_id).first()
    return float(inventory_item.current_quantity) if inventory_item else 0.0

def get_returnable_stock(item_id: int, db: Session) -> float:
    """Get returnable stock for an item"""
    inventory_item = db.query(InventoryItem).filter(InventoryItem.item_master_id == item_id).first()
    return float(inventory_item.returnable_quantity) if inventory_item else 0.0

# ============================
# Continue with the rest of the API routes and application code...
# (The rest of the code remains the same as in the original file)
# ============================

# Note: For brevity, I'm showing just the fixed model relationships.
# The rest of the application code (API routes, frontend HTML, etc.) 
# remains exactly the same as in your original file.

# ============================
# API ROUTES
# ============================

# Authentication API Routes
@app.post("/login")
async def login(request: Request, employee_id: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.employee_id == employee_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    session_id = create_session(user.id)
    
    response = {
        "id": user.id,
        "employee_id": user.employee_id,
        "name": user.name,
        "email": user.email,
        "is_admin": user.is_admin
    }
    
    resp = JSONResponse(response)
    resp.set_cookie(key="session_id", value=session_id, httponly=True)
    return resp

@app.post("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id in active_sessions:
        del active_sessions[session_id]
    
    resp = JSONResponse({"message": "Logged out"})
    resp.delete_cookie("session_id")
    return resp

# Database Status API Routes
@app.get("/api/database-status")
async def get_database_status():
    """Get database schema validation status"""
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        expected_tables = [
            'divisions', 'departments', 'users', 'categories', 'item_master',
            'inventory_items', 'orders', 'order_items', 'inventory_transactions'
        ]
        
        missing_tables = [table for table in expected_tables if table not in existing_tables]
        
        # Check for missing columns
        missing_columns_info = []
        for table_name in expected_tables:
            if table_name in existing_tables:
                existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
                expected_columns = {
                    'divisions': ['id', 'name', 'description', 'is_default', 'created_at'],
                    'departments': ['id', 'name', 'description', 'division_id', 'created_at'],
                    'users': ['id', 'employee_id', 'name', 'email', 'password_hash', 'department_id', 'is_admin', 'is_active', 'created_at'],
                    'categories': ['id', 'name', 'description', 'parent_id', 'is_active', 'created_at', 'created_by'],
                    'item_master': ['id', 'item_code', 'item_name', 'description', 'category_id', 'unit_of_measure', 'min_stock_level', 'max_stock_level', 'standard_cost', 'location', 'barcode', 'manufacturer', 'model_number', 'specifications', 'warranty_months', 'is_returnable', 'is_active', 'created_at', 'created_by', 'updated_at', 'updated_by'],
                    'inventory_items': ['id', 'item_master_id', 'current_quantity', 'reserved_quantity', 'returnable_quantity', 'available_quantity', 'last_updated'],
                    'orders': ['id', 'order_number', 'customer_name', 'customer_contact', 'order_date', 'expected_delivery_date', 'order_status', 'total_amount', 'notes', 'created_by', 'created_at', 'updated_at'],
                    'order_items': ['id', 'order_id', 'item_master_id', 'requested_quantity', 'fulfilled_quantity', 'returnable_quantity', 'unit_price', 'total_price', 'status'],
                    'inventory_transactions': ['id', 'transaction_number', 'item_master_id', 'order_id', 'transaction_type', 'transaction_sub_type', 'quantity', 'returnable_quantity', 'unit_cost', 'total_cost', 'reference_number', 'vendor_customer', 'remarks', 'transaction_date', 'expected_return_date', 'user_id', 'status', 'confirmed_at', 'confirmed_by', 'created_at']
                }
                
                if table_name in expected_columns:
                    missing_cols = [col for col in expected_columns[table_name] if col not in existing_columns]
                    if missing_cols:
                        missing_columns_info.append(f"{table_name}: {missing_cols}")
        
        return {
            "status": "healthy" if not missing_tables and not missing_columns_info else "needs_migration",
            "existing_tables": len(existing_tables),
            "expected_tables": len(expected_tables),
            "missing_tables": missing_tables,
            "missing_columns": missing_columns_info,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }

@app.get("/api/health")
async def health_check():
    """Application health check"""
    try:
        # Test database connection
        db = SessionLocal()
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Division Management API Routes
@app.get("/divisions")
async def get_divisions(db: Session = Depends(get_db)):
    divisions = db.query(Division).all()
    return [
        {
            "id": div.id,
            "name": div.name,
            "description": div.description,
            "is_default": div.is_default
        }
        for div in divisions
    ]

@app.get("/admin/divisions-with-departments")
async def get_divisions_with_departments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    divisions = db.query(Division).all()
    result = []
    
    for div in divisions:
        dept_count = db.query(Department).filter(Department.division_id == div.id).count()
        result.append({
            "id": div.id,
            "name": div.name,
            "description": div.description,
            "is_default": div.is_default,
            "department_count": dept_count,
            "created_at": div.created_at
        })
    
    return result

@app.post("/admin/divisions")
async def create_division(
    name: str = Form(...),
    description: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing = db.query(Division).filter(Division.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Division with this name already exists")
    
    division = Division(name=name, description=description)
    db.add(division)
    db.commit()
    
    return {"message": "Division created successfully", "division_id": division.id}

# Department Management API Routes
@app.get("/departments")
async def get_departments(db: Session = Depends(get_db)):
    departments = db.query(Department).all()
    return [
        {
            "id": dept.id,
            "name": dept.name,
            "description": dept.description,
            "division": {"id": dept.division.id, "name": dept.division.name} if dept.division else None
        }
        for dept in departments
    ]

@app.get("/admin/departments-with-users")
async def get_departments_with_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    departments = db.query(Department).all()
    result = []
    
    for dept in departments:
        user_count = db.query(User).filter(User.department_id == dept.id).count()
        result.append({
            "id": dept.id,
            "name": dept.name,
            "description": dept.description,
            "division": {"id": dept.division.id, "name": dept.division.name} if dept.division else None,
            "user_count": user_count,
            "created_at": dept.created_at
        })
    
    return result

@app.post("/admin/departments")
async def create_department(
    name: str = Form(...),
    description: str = Form(""),
    division_id: int = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing = db.query(Department).filter(Department.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Department with this name already exists")
    
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")
    
    department = Department(name=name, description=description, division_id=division_id)
    db.add(department)
    db.commit()
    
    return {"message": "Department created successfully", "department_id": department.id}

# User Management API Routes
@app.get("/admin/users")
async def get_all_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = db.query(User).all()
    return [
        {
            "id": user.id,
            "employee_id": user.employee_id,
            "name": user.name,
            "email": user.email,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
            "department": {"id": user.department.id, "name": user.department.name} if user.department else None,
            "created_at": user.created_at
        }
        for user in users
    ]

@app.get("/users")
async def get_users_for_selection(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_active == True).all()
    return [
        {
            "id": user.id,
            "name": user.name,
            "employee_id": user.employee_id
        }
        for user in users
    ]

@app.post("/admin/users")
async def create_user(
    employee_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    department_id: int = Form(...),
    is_admin: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if employee_id or email already exists
    existing_emp = db.query(User).filter(User.employee_id == employee_id).first()
    if existing_emp:
        raise HTTPException(status_code=400, detail="Employee ID already exists")
    
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Check if department exists
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    hashed_password = hash_password(password)
    
    user = User(
        employee_id=employee_id,
        name=name,
        email=email,
        password_hash=hashed_password,
        department_id=department_id,
        is_admin=is_admin
    )
    
    db.add(user)
    db.commit()
    
    return {"message": "User created successfully", "user_id": user.id}

# Category Management API Routes
@app.get("/categories")
async def get_categories(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    categories = db.query(Category).filter(Category.is_active == True).all()
    
    def build_category_tree(parent_id=None):
        cats = [cat for cat in categories if cat.parent_id == parent_id]
        result = []
        for cat in cats:
            cat_data = {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "parent_id": cat.parent_id,
                "created_at": cat.created_at,
                "children": build_category_tree(cat.id)
            }
            result.append(cat_data)
        return result
    
    return build_category_tree()

@app.post("/categories")
async def create_category(
    name: str = Form(...),
    description: str = Form(""),
    parent_id: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    parent_category_id = int(parent_id) if parent_id else None
    
    existing = db.query(Category).filter(Category.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category with this name already exists")
    
    category = Category(
        name=name,
        description=description,
        parent_id=parent_category_id,
        created_by=current_user.id
    )
    
    db.add(category)
    db.commit()
    
    return {"message": "Category created successfully", "category_id": category.id}


@app.get("/orders/pending-fulfillment")
async def get_pending_fulfillment_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get orders that are pending fulfillment"""
    orders = db.query(Order).filter(
        Order.order_status == 'PENDING'
    ).order_by(Order.created_at.desc()).all()
    
    return [
        {
            "id": order.id,
            "order_number": order.order_number,
            "customer_name": order.customer_name,
            "customer_contact": order.customer_contact,
            "order_date": order.order_date,
            "expected_delivery_date": order.expected_delivery_date,
            "total_amount": float(order.total_amount),
            "notes": order.notes,
            "order_items": [
                {
                    "id": item.id,
                    "item_master_id": item.item_master_id,
                    "item_code": item.item_master.item_code,
                    "item_name": item.item_master.item_name,
                    "is_returnable": item.item_master.is_returnable,
                    "unit_of_measure": item.item_master.unit_of_measure,
                    "requested_quantity": float(item.requested_quantity),
                    "fulfilled_quantity": float(item.fulfilled_quantity),
                    "unit_price": float(item.unit_price),
                    "total_price": float(item.total_price),
                    "status": item.status,
                    "current_stock": get_current_stock(item.item_master_id, db),
                    "available_stock": get_available_stock(item.item_master_id, db)
                }
                for item in order.order_items
            ],
            "created_at": order.created_at
        }
        for order in orders
    ]

@app.post("/orders/{order_id}/fulfill-item")
async def fulfill_order_item(
    order_id: int,
    order_item_id: int = Form(...),
    fulfill_quantity: float = Form(...),
    extra_quantity: float = Form(0),
    expected_return_date: str = Form(""),
    remarks: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fulfill a specific item in an order"""
    try:
        # Validate order and order item
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        order_item = db.query(OrderItem).filter(
            OrderItem.id == order_item_id,
            OrderItem.order_id == order_id
        ).first()
        if not order_item:
            raise HTTPException(status_code=404, detail="Order item not found")
        
        if order.order_status != 'PENDING':
            raise HTTPException(status_code=400, detail="Order is not in pending status")
        
        # Check if fulfill quantity is valid
        remaining_qty = order_item.requested_quantity - order_item.fulfilled_quantity
        if fulfill_quantity > remaining_qty:
            raise HTTPException(
                status_code=400, 
                detail=f"Fulfill quantity ({fulfill_quantity}) exceeds remaining quantity ({remaining_qty})"
            )
        
        # Check stock availability
        total_needed = fulfill_quantity + extra_quantity
        available_stock = get_available_stock(order_item.item_master_id, db)
        
        if total_needed > available_stock:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient stock. Available: {available_stock}, Needed: {total_needed}"
            )
        
        # Parse expected return date
        expected_return = None
        if expected_return_date:
            try:
                expected_return = datetime.strptime(expected_return_date, "%Y-%m-%d")
            except ValueError:
                pass
        
        # Create fulfillment transaction
        transaction = InventoryTransaction(
            transaction_number=generate_transaction_number(),
            item_master_id=order_item.item_master_id,
            order_id=order_id,
            transaction_type='OUT',
            transaction_sub_type='ORDER_FULFILLMENT',
            quantity=total_needed,
            returnable_quantity=extra_quantity,
            unit_cost=order_item.unit_price,
            total_cost=total_needed * order_item.unit_price,
            reference_number=order.order_number,
            vendor_customer=order.customer_name,
            remarks=remarks or f"Order fulfillment for {order.order_number}",
            expected_return_date=expected_return,
            user_id=current_user.id,
            status='CONFIRMED'  # Auto-confirm fulfillment transactions
        )
        
        db.add(transaction)
        db.flush()
        
        # Update inventory
        inventory_item = db.query(InventoryItem).filter(
            InventoryItem.item_master_id == order_item.item_master_id
        ).first()
        
        if inventory_item:
            inventory_item.current_quantity -= total_needed
            if extra_quantity > 0:
                inventory_item.returnable_quantity += extra_quantity
            inventory_item.available_quantity = inventory_item.current_quantity - inventory_item.reserved_quantity
            inventory_item.last_updated = datetime.utcnow()
        
        # Update order item
        order_item.fulfilled_quantity += fulfill_quantity
        if extra_quantity > 0:
            order_item.returnable_quantity += extra_quantity
        
        # Update order item status
        if order_item.fulfilled_quantity >= order_item.requested_quantity:
            order_item.status = 'FULFILLED'
        else:
            order_item.status = 'PARTIAL'
        
        # Check if entire order is fulfilled
        all_items_fulfilled = all(
            item.fulfilled_quantity >= item.requested_quantity 
            for item in order.order_items
        )
        
        if all_items_fulfilled:
            order.order_status = 'FULFILLED'
        else:
            order.order_status = 'PROCESSING'
        
        order.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": "Order item fulfilled successfully",
            "transaction_id": transaction.id,
            "transaction_number": transaction.transaction_number,
            "order_status": order.order_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error fulfilling order item: {str(e)}")

@app.post("/orders/{order_id}/bulk-fulfill")
async def bulk_fulfill_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fulfill entire order at once (all items with requested quantities)"""
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        if order.order_status != 'PENDING':
            raise HTTPException(status_code=400, detail="Order is not in pending status")
        
        # Check stock availability for all items
        stock_issues = []
        for order_item in order.order_items:
            remaining_qty = order_item.requested_quantity - order_item.fulfilled_quantity
            if remaining_qty > 0:
                available_stock = get_available_stock(order_item.item_master_id, db)
                if remaining_qty > available_stock:
                    stock_issues.append({
                        "item_code": order_item.item_master.item_code,
                        "item_name": order_item.item_master.item_name,
                        "needed": remaining_qty,
                        "available": available_stock
                    })
        
        if stock_issues:
            error_msg = "Insufficient stock for the following items:\\n"
            for issue in stock_issues:
                error_msg += f"- {issue['item_code']}: Need {issue['needed']}, Available {issue['available']}\\n"
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Process fulfillment for each item
        fulfilled_items = []
        for order_item in order.order_items:
            remaining_qty = order_item.requested_quantity - order_item.fulfilled_quantity
            if remaining_qty > 0:
                # Create fulfillment transaction
                transaction = InventoryTransaction(
                    transaction_number=generate_transaction_number(),
                    item_master_id=order_item.item_master_id,
                    order_id=order_id,
                    transaction_type='OUT',
                    transaction_sub_type='ORDER_FULFILLMENT',
                    quantity=remaining_qty,
                    returnable_quantity=0,
                    unit_cost=order_item.unit_price,
                    total_cost=remaining_qty * order_item.unit_price,
                    reference_number=order.order_number,
                    vendor_customer=order.customer_name,
                    remarks=f"Bulk fulfillment for {order.order_number}",
                    user_id=current_user.id,
                    status='CONFIRMED'
                )
                
                db.add(transaction)
                db.flush()
                
                # Update inventory
                inventory_item = db.query(InventoryItem).filter(
                    InventoryItem.item_master_id == order_item.item_master_id
                ).first()
                
                if inventory_item:
                    inventory_item.current_quantity -= remaining_qty
                    inventory_item.available_quantity = inventory_item.current_quantity - inventory_item.reserved_quantity
                    inventory_item.last_updated = datetime.utcnow()
                
                # Update order item
                order_item.fulfilled_quantity = order_item.requested_quantity
                order_item.status = 'FULFILLED'
                
                fulfilled_items.append({
                    "item_code": order_item.item_master.item_code,
                    "quantity": remaining_qty,
                    "transaction_number": transaction.transaction_number
                })
        
        # Update order status
        order.order_status = 'FULFILLED'
        order.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": "Order fulfilled successfully",
            "fulfilled_items": fulfilled_items,
            "order_status": order.order_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error fulfilling order: {str(e)}")



@app.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Check if category has items
    item_count = db.query(ItemMaster).filter(ItemMaster.category_id == category_id).count()
    if item_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete category with {item_count} items")
    
    # Check if category has sub-categories
    child_count = db.query(Category).filter(Category.parent_id == category_id).count()
    if child_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete category with {child_count} sub-categories")
    
    category.is_active = False
    db.commit()
    
    return {"message": "Category deleted successfully"}

# Item Master Management API Routes
@app.get("/items")
async def get_items(
    category_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(ItemMaster).filter(ItemMaster.is_active == True)
    
    if category_id:
        query = query.filter(ItemMaster.category_id == category_id)
    
    items = query.all()
    
    return [
        {
            "id": item.id,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "category": {"id": item.category.id, "name": item.category.name} if item.category else None,
            "unit_of_measure": item.unit_of_measure,
            "min_stock_level": float(item.min_stock_level) if item.min_stock_level else 0,
            "max_stock_level": float(item.max_stock_level) if item.max_stock_level else 0,
            "standard_cost": float(item.standard_cost) if item.standard_cost else 0,
            "location": item.location,
            "manufacturer": item.manufacturer,
            "model_number": item.model_number,
            "is_returnable": item.is_returnable,
            "current_stock": get_current_stock(item.id, db),
            "returnable_stock": get_returnable_stock(item.id, db),
            "created_at": item.created_at
        }
        for item in items
    ]

@app.post("/items")
async def create_item(
    item_code: str = Form(...),
    item_name: str = Form(...),
    description: str = Form(""),
    category_id: int = Form(...),
    unit_of_measure: str = Form(...),
    min_stock_level: float = Form(0),
    max_stock_level: float = Form(0),
    standard_cost: float = Form(0),
    location: str = Form(""),
    manufacturer: str = Form(""),
    model_number: str = Form(""),
    specifications: str = Form(""),
    warranty_months: int = Form(0),
    is_returnable: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if item code exists
    existing = db.query(ItemMaster).filter(ItemMaster.item_code == item_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Item code already exists")
    
    # Check if category exists
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    item = ItemMaster(
        item_code=item_code,
        item_name=item_name,
        description=description,
        category_id=category_id,
        unit_of_measure=unit_of_measure,
        min_stock_level=min_stock_level,
        max_stock_level=max_stock_level,
        standard_cost=standard_cost,
        location=location,
        manufacturer=manufacturer,
        model_number=model_number,
        specifications=specifications,
        warranty_months=warranty_months,
        is_returnable=is_returnable,
        created_by=current_user.id,
        updated_by=current_user.id
    )
    
    db.add(item)
    db.commit()
    db.refresh(item)
    
    # Create inventory item record
    inventory_item = InventoryItem(
        item_master_id=item.id,
        current_quantity=0,
        reserved_quantity=0,
        returnable_quantity=0,
        available_quantity=0
    )
    db.add(inventory_item)
    db.commit()
    
    return {"message": "Item created successfully", "item_id": item.id}

# Order Management API Routes
@app.get("/orders")
async def get_orders(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Order)
    
    if status:
        query = query.filter(Order.order_status == status)
    
    orders = query.order_by(Order.created_at.desc()).all()
    
    return [
        {
            "id": order.id,
            "order_number": order.order_number,
            "customer_name": order.customer_name,
            "customer_contact": order.customer_contact,
            "order_date": order.order_date,
            "expected_delivery_date": order.expected_delivery_date,
            "order_status": order.order_status,
            "total_amount": float(order.total_amount),
            "notes": order.notes,
            "created_by": {"name": order.created_by_user.name} if order.created_by_user else None,
            "item_count": len(order.order_items),
            "created_at": order.created_at
        }
        for order in orders
    ]

@app.post("/orders")
async def create_order(
    customer_name: str = Form(...),
    customer_contact: str = Form(...),
    expected_delivery_date: str = Form(""),
    notes: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    expected_delivery = None
    if expected_delivery_date:
        try:
            expected_delivery = datetime.strptime(expected_delivery_date, "%Y-%m-%d")
        except ValueError:
            pass
    
    order = Order(
        order_number=generate_order_number(),
        customer_name=customer_name,
        customer_contact=customer_contact,
        expected_delivery_date=expected_delivery,
        notes=notes,
        created_by=current_user.id
    )
    
    db.add(order)
    db.commit()
    db.refresh(order)
    
    return {"message": "Order created successfully", "order_id": order.id, "order_number": order.order_number}

@app.get("/orders/{order_id}")
async def get_order_details(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_name": order.customer_name,
        "customer_contact": order.customer_contact,
        "order_date": order.order_date,
        "expected_delivery_date": order.expected_delivery_date,
        "order_status": order.order_status,
        "total_amount": float(order.total_amount),
        "notes": order.notes,
        "created_by": {"name": order.created_by_user.name} if order.created_by_user else None,
        "order_items": [
            {
                "id": item.id,
                "item": {
                    "id": item.item_master.id,
                    "item_code": item.item_master.item_code,
                    "item_name": item.item_master.item_name,
                    "is_returnable": item.item_master.is_returnable
                },
                "requested_quantity": float(item.requested_quantity),
                "fulfilled_quantity": float(item.fulfilled_quantity),
                "returnable_quantity": float(item.returnable_quantity),
                "unit_price": float(item.unit_price),
                "total_price": float(item.total_price),
                "status": item.status
            }
            for item in order.order_items
        ],
        "created_at": order.created_at
    }

@app.post("/orders/{order_id}/items")
async def add_order_item(
    order_id: int,
    item_master_id: int = Form(...),
    requested_quantity: float = Form(...),
    unit_price: float = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.order_status != 'PENDING':
        raise HTTPException(status_code=400, detail="Cannot modify confirmed order")
    
    item = db.query(ItemMaster).filter(ItemMaster.id == item_master_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    total_price = requested_quantity * unit_price
    
    order_item = OrderItem(
        order_id=order_id,
        item_master_id=item_master_id,
        requested_quantity=requested_quantity,
        unit_price=unit_price,
        total_price=total_price
    )
    
    db.add(order_item)
    
    # Update order total
    order.total_amount += total_price
    db.commit()
    
    return {"message": "Item added to order successfully"}

@app.delete("/orders/{order_id}")
async def delete_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        if order.order_status not in ['PENDING', 'CANCELLED']:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete orders with status '{order.order_status}'"
            )
        
        confirmed_transactions = db.query(InventoryTransaction).filter(
            InventoryTransaction.order_id == order_id,
            InventoryTransaction.status == 'CONFIRMED'
        ).count()
        
        if confirmed_transactions > 0:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete order with confirmed transactions"
            )
        
        # Delete order items
        db.query(OrderItem).filter(OrderItem.order_id == order_id).delete()
        
        # Delete pending transactions
        db.query(InventoryTransaction).filter(
            InventoryTransaction.order_id == order_id,
            InventoryTransaction.status == 'PENDING'
        ).delete()
        
        # Delete the order
        order_number = order.order_number
        db.delete(order)
        db.commit()
        
        return {"message": "Order deleted successfully", "order_number": order_number}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting order: {str(e)}")

# Inventory Transaction Routes
@app.get("/inventory/transactions")
async def get_inventory_transactions(
    item_id: Optional[int] = None,
    transaction_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(InventoryTransaction)
    
    if item_id:
        query = query.filter(InventoryTransaction.item_master_id == item_id)
    if transaction_type:
        query = query.filter(InventoryTransaction.transaction_type == transaction_type)
    if status:
        query = query.filter(InventoryTransaction.status == status)
    
    transactions = query.order_by(InventoryTransaction.created_at.desc()).all()
    
    return [
        {
            "id": txn.id,
            "transaction_number": txn.transaction_number,
            "item": {
                "id": txn.item_master.id,
                "item_code": txn.item_master.item_code,
                "item_name": txn.item_master.item_name
            } if txn.item_master else None,
            "order": {
                "id": txn.order.id,
                "order_number": txn.order.order_number,
                "customer_name": txn.order.customer_name
            } if txn.order else None,
            "transaction_type": txn.transaction_type,
            "transaction_sub_type": txn.transaction_sub_type,
            "quantity": float(txn.quantity),
            "returnable_quantity": float(txn.returnable_quantity),
            "unit_cost": float(txn.unit_cost) if txn.unit_cost else 0,
            "total_cost": float(txn.total_cost) if txn.total_cost else 0,
            "reference_number": txn.reference_number,
            "vendor_customer": txn.vendor_customer,
            "remarks": txn.remarks,
            "transaction_date": txn.transaction_date,
            "expected_return_date": txn.expected_return_date,
            "status": txn.status,
            "user": {"name": txn.user.name} if txn.user else None,
            "created_at": txn.created_at
        }
        for txn in transactions
    ]

@app.post("/inventory/transactions")
async def create_inventory_transaction(
    item_master_id: int = Form(...),
    transaction_type: str = Form(...),
    transaction_sub_type: str = Form(...),
    quantity: float = Form(...),
    returnable_quantity: float = Form(0),
    unit_cost: float = Form(0),
    reference_number: str = Form(""),
    vendor_customer: str = Form(""),
    remarks: str = Form(""),
    expected_return_date: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validate item exists
    item = db.query(ItemMaster).filter(ItemMaster.id == item_master_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Parse expected return date
    expected_return = None
    if expected_return_date:
        try:
            expected_return = datetime.strptime(expected_return_date, "%Y-%m-%d")
        except ValueError:
            pass
    
    # Calculate total cost
    total_cost = quantity * unit_cost
    
    transaction = InventoryTransaction(
        transaction_number=generate_transaction_number(),
        item_master_id=item_master_id,
        transaction_type=transaction_type,
        transaction_sub_type=transaction_sub_type,
        quantity=quantity,
        returnable_quantity=returnable_quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
        reference_number=reference_number,
        vendor_customer=vendor_customer,
        remarks=remarks,
        expected_return_date=expected_return,
        user_id=current_user.id
    )
    
    db.add(transaction)
    db.commit()
    
    return {"message": "Transaction created successfully", "transaction_id": transaction.id}

@app.post("/inventory/transactions/{transaction_id}/confirm")
async def confirm_inventory_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    transaction = db.query(InventoryTransaction).filter(InventoryTransaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction.status != 'PENDING':
        raise HTTPException(status_code=400, detail="Transaction already processed")
    
    # Update inventory levels
    inventory_item = db.query(InventoryItem).filter(
        InventoryItem.item_master_id == transaction.item_master_id
    ).first()
    
    if not inventory_item:
        # Create inventory item if doesn't exist
        inventory_item = InventoryItem(
            item_master_id=transaction.item_master_id,
            current_quantity=0,
            reserved_quantity=0,
            returnable_quantity=0,
            available_quantity=0
        )
        db.add(inventory_item)
        db.flush()
    
    # Update quantities based on transaction type
    if transaction.transaction_type == 'IN':
        inventory_item.current_quantity += transaction.quantity
        if transaction.transaction_sub_type == 'CUSTOMER_RETURN':
            inventory_item.returnable_quantity -= transaction.quantity
    elif transaction.transaction_type == 'OUT':
        if inventory_item.current_quantity < transaction.quantity:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        inventory_item.current_quantity -= transaction.quantity
        if transaction.returnable_quantity > 0:
            inventory_item.returnable_quantity += transaction.returnable_quantity
    elif transaction.transaction_type == 'ADJUST':
        inventory_item.current_quantity = transaction.quantity
    
    inventory_item.available_quantity = inventory_item.current_quantity - inventory_item.reserved_quantity
    
    # Update transaction status
    transaction.status = 'CONFIRMED'
    transaction.confirmed_at = datetime.utcnow()
    transaction.confirmed_by = current_user.id
    
    db.commit()
    
    return {"message": "Transaction confirmed successfully"}

# Dashboard API Routes
@app.get("/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stats = {
        "total_categories": db.query(Category).filter(Category.is_active == True).count(),
        "total_items": db.query(ItemMaster).filter(ItemMaster.is_active == True).count(),
        "total_transactions": db.query(InventoryTransaction).count(),
        "pending_transactions": db.query(InventoryTransaction).filter(InventoryTransaction.status == 'PENDING').count(),
        "total_orders": db.query(Order).count(),
        "pending_orders": db.query(Order).filter(Order.order_status == 'PENDING').count(),
        "low_stock_items": db.query(ItemMaster).join(InventoryItem).filter(
            InventoryItem.current_quantity <= ItemMaster.min_stock_level,
            ItemMaster.min_stock_level > 0
        ).count(),
        "returnable_items": db.query(InventoryTransaction).filter(
            InventoryTransaction.returnable_quantity > 0,
            InventoryTransaction.status == 'CONFIRMED',
            InventoryTransaction.transaction_type == 'OUT'
        ).count()
    }
    
    return stats

@app.get("/dashboard/low-stock")
async def get_low_stock_items(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(ItemMaster).join(InventoryItem).filter(
        InventoryItem.current_quantity <= ItemMaster.min_stock_level,
        ItemMaster.min_stock_level > 0,
        ItemMaster.is_active == True
    ).all()
    
    return [
        {
            "id": item.id,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "current_stock": float(item.inventory_items[0].current_quantity) if item.inventory_items else 0,
            "min_stock_level": float(item.min_stock_level),
            "category": {"name": item.category.name} if item.category else None
        }
        for item in items
    ]

# Returnable Items Management
@app.get("/inventory/returnable-items")
async def get_returnable_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    transactions = db.query(InventoryTransaction).filter(
        InventoryTransaction.returnable_quantity > 0,
        InventoryTransaction.status == 'CONFIRMED',
        InventoryTransaction.transaction_type == 'OUT'
    ).all()
    
    returnable_items = []
    for txn in transactions:
        # Check if any items have been returned
        returned_qty = db.query(func.sum(InventoryTransaction.quantity)).filter(
            InventoryTransaction.reference_number == txn.transaction_number,
            InventoryTransaction.transaction_sub_type == 'CUSTOMER_RETURN',
            InventoryTransaction.status == 'CONFIRMED'
        ).scalar() or 0
        
        outstanding_qty = float(txn.returnable_quantity) - float(returned_qty)
        
        if outstanding_qty > 0:
            returnable_items.append({
                "transaction_id": txn.id,
                "transaction_number": txn.transaction_number,
                "item": {
                    "id": txn.item_master.id,
                    "item_code": txn.item_master.item_code,
                    "item_name": txn.item_master.item_name
                },
                "customer_name": txn.vendor_customer,
                "total_returnable": float(txn.returnable_quantity),
                "returned_quantity": float(returned_qty),
                "outstanding_quantity": outstanding_qty,
                "expected_return_date": txn.expected_return_date,
                "transaction_date": txn.transaction_date,
                "is_overdue": txn.expected_return_date and txn.expected_return_date < datetime.utcnow().date() if txn.expected_return_date else False
            })
    
    return returnable_items

@app.post("/inventory/process-return")
async def process_return(
    transaction_id: int = Form(...),
    returned_quantity: float = Form(...),
    condition: str = Form(...),
    remarks: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get original transaction
    original_txn = db.query(InventoryTransaction).filter(InventoryTransaction.id == transaction_id).first()
    if not original_txn:
        raise HTTPException(status_code=404, detail="Original transaction not found")
    
    # Validate return quantity
    returned_so_far = db.query(func.sum(InventoryTransaction.quantity)).filter(
        InventoryTransaction.reference_number == original_txn.transaction_number,
        InventoryTransaction.transaction_sub_type == 'CUSTOMER_RETURN',
        InventoryTransaction.status == 'CONFIRMED'
    ).scalar() or 0
    
    if returned_quantity > (original_txn.returnable_quantity - returned_so_far):
        raise HTTPException(status_code=400, detail="Return quantity exceeds outstanding returnable quantity")
    
    # Create return transaction
    return_transaction = InventoryTransaction(
        transaction_number=generate_transaction_number(),
        item_master_id=original_txn.item_master_id,
        order_id=original_txn.order_id,
        transaction_type='IN',
        transaction_sub_type='CUSTOMER_RETURN',
        quantity=returned_quantity,
        unit_cost=original_txn.unit_cost,
        total_cost=returned_quantity * original_txn.unit_cost,
        reference_number=original_txn.transaction_number,
        vendor_customer=original_txn.vendor_customer,
        remarks=f"Return - Condition: {condition}. {remarks}",
        user_id=current_user.id,
        status='PENDING'
    )
    
    db.add(return_transaction)
    db.commit()
    
    return {"message": "Return processed successfully", "transaction_id": return_transaction.id}

# Order Fulfillment Routes
@app.post("/inventory/transactions/order-fulfillment")
async def create_order_fulfillment_transaction(
    order_id: int = Form(...),
    item_master_id: int = Form(...),
    requested_quantity: float = Form(...),
    extra_quantity: float = Form(0),
    unit_cost: float = Form(0),
    remarks: str = Form(""),
    expected_return_date: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validate order and item
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    item = db.query(ItemMaster).filter(ItemMaster.id == item_master_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    total_quantity = requested_quantity + extra_quantity
    
    # Check stock availability
    inventory_item = db.query(InventoryItem).filter(
        InventoryItem.item_master_id == item_master_id
    ).first()
    
    if not inventory_item:
        raise HTTPException(status_code=400, detail="Item not found in inventory")
    
    if inventory_item.available_quantity < total_quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")
    
    # Parse expected return date
    expected_return = None
    if expected_return_date:
        try:
            expected_return = datetime.strptime(expected_return_date, "%Y-%m-%d")
        except ValueError:
            pass
    
    # Create transaction
    transaction = InventoryTransaction(
        transaction_number=generate_transaction_number(),
        item_master_id=item_master_id,
        order_id=order_id,
        transaction_type='OUT',
        transaction_sub_type='ORDER_FULFILLMENT',
        quantity=total_quantity,
        returnable_quantity=extra_quantity,
        unit_cost=unit_cost,
        total_cost=total_quantity * unit_cost,
        reference_number=order.order_number,
        vendor_customer=order.customer_name,
        remarks=remarks,
        expected_return_date=expected_return,
        user_id=current_user.id
    )
    
    db.add(transaction)
    db.commit()
    
    return {"message": "Order fulfillment transaction created successfully", "transaction_id": transaction.id}

@app.post("/orders/{order_id}/fulfill")
async def fulfill_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.order_status != 'PENDING':
        raise HTTPException(status_code=400, detail="Order already processed")
    
    # Check stock availability for all items
    for order_item in order.order_items:
        inventory_item = db.query(InventoryItem).filter(
            InventoryItem.item_master_id == order_item.item_master_id
        ).first()
        
        if not inventory_item or inventory_item.available_quantity < order_item.requested_quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient stock for item {order_item.item_master.item_code}"
            )
    
    # Process fulfillment for each item
    for order_item in order.order_items:
        # Create fulfillment transaction
        transaction = InventoryTransaction(
            transaction_number=generate_transaction_number(),
            item_master_id=order_item.item_master_id,
            order_id=order_id,
            transaction_type='OUT',
            transaction_sub_type='ORDER_FULFILLMENT',
            quantity=order_item.requested_quantity,
            returnable_quantity=0,
            unit_cost=order_item.unit_price,
            total_cost=order_item.total_price,
            reference_number=order.order_number,
            vendor_customer=order.customer_name,
            remarks=f"Order fulfillment for {order.order_number}",
            user_id=current_user.id,
            status='CONFIRMED'
        )
        
        db.add(transaction)
        
        # Update inventory
        inventory_item = db.query(InventoryItem).filter(
            InventoryItem.item_master_id == order_item.item_master_id
        ).first()
        
        inventory_item.current_quantity -= order_item.requested_quantity
        inventory_item.available_quantity = inventory_item.current_quantity - inventory_item.reserved_quantity
        
        # Update order item status
        order_item.fulfilled_quantity = order_item.requested_quantity
        order_item.status = 'FULFILLED'
    
    # Update order status
    order.order_status = 'FULFILLED'
    order.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "Order fulfilled successfully"}

# ============================
# STARTUP EVENT
# ============================

@app.on_event("startup")
async def startup_event():
    """Enhanced startup event with comprehensive database validation"""
    logger.info("🚀 Starting DigiAssets Application...")
    
    # Initialize database with validation
    success = create_database()
    
    if success:
        logger.info("🎉 Application started successfully!")
        logger.info("📊 Database schema validated and ready")
        logger.info("🔐 Default admin credentials: ADMIN001 / admin123")
        logger.info("🌐 Application available at: http://localhost:8000")
    else:
        logger.error("❌ Application startup failed due to database issues")

# ============================
# COMPLETE FRONTEND HTML
# ============================

@app.get("/", response_class=HTMLResponse)
async def get_frontend():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DigiAssets - Complete Digital Inventory Management</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }

            /* Status indicator */
            .status-indicator {
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                z-index: 1000;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            
            .status-healthy { background: #4caf50; color: white; }
            .status-warning { background: #ff9800; color: white; }
            .status-error { background: #f44336; color: white; }

            .btn { 
                background: linear-gradient(135deg, #667eea, #764ba2); 
                color: white; 
                padding: 12px 24px; 
                border: none; 
                border-radius: 8px; 
                cursor: pointer; 
                margin: 4px; 
                font-weight: 500;
                transition: all 0.3s ease;
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }

            .btn:hover { 
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
            }

            .btn-success { background: linear-gradient(135deg, #56ab2f, #a8e6cf); }
            .btn-danger { background: linear-gradient(135deg, #ff416c, #ff4b2b); }
            .btn-warning { background: linear-gradient(135deg, #f7971e, #ffd200); }
            .btn-info { background: linear-gradient(135deg, #00d2ff, #3a7bd5); }
            .btn-purple { background: linear-gradient(135deg, #9b59b6, #8e44ad); }

            .header { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; 
                padding: 20px 0; 
                margin-bottom: 20px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }

            .header h1 { 
                text-align: center; 
                margin: 0;
                font-size: 1.8em;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }

            .login-container { 
                max-width: 400px; 
                margin: 100px auto; 
                background: white; 
                padding: 40px; 
                border-radius: 12px; 
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            }

            .login-background {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                z-index: -1;
            }

            .digiassets-logo {
                text-align: center;
                margin-bottom: 30px;
            }

            .digiassets-logo h1 {
                font-size: 2.5em;
                background: linear-gradient(135deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                font-weight: bold;
            }

            .form-group { margin-bottom: 15px; }
            .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
            .form-group input, .form-group select, .form-group textarea { 
                width: 100%; 
                padding: 10px; 
                border: 1px solid #ddd; 
                border-radius: 4px; 
            }

            .nav-tabs { 
                display: flex; 
                background: white; 
                border-radius: 8px; 
                margin-bottom: 20px; 
                overflow: hidden; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
            }
            .nav-tab { 
                flex: 1; 
                padding: 15px; 
                text-align: center; 
                cursor: pointer; 
                border: none; 
                background: #ecf0f1; 
                transition: all 0.3s ease;
            }
            .nav-tab.active { background: #3498db; color: white; }
            .nav-tab:hover { background: #d5dbdb; }

            .content-area { 
                background: white; 
                padding: 30px; 
                border-radius: 12px; 
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }

            .content-area h3 {
                color: #2c3e50;
                border-bottom: 3px solid #667eea;
                padding-bottom: 10px;
                margin-bottom: 25px;
                font-size: 1.5em;
            }

            .stats-grid { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                gap: 20px; 
                margin-bottom: 30px; 
            }
            .stat-card { 
                background: linear-gradient(135deg, #3498db, #2980b9); 
                color: white; 
                padding: 20px; 
                border-radius: 8px; 
                text-align: center; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                transition: transform 0.3s ease;
            }
            .stat-card:hover { transform: translateY(-5px); }
            .stat-card h3 { margin: 0 0 10px 0; font-size: 2em; }
            .stat-card p { margin: 0; opacity: 0.9; }

            .item-grid { 
                display: grid; 
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); 
                gap: 20px; 
                margin-top: 20px; 
            }
            .item-card { 
                border: 1px solid #ddd; 
                border-radius: 8px; 
                padding: 15px; 
                background: white; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                transition: transform 0.3s ease;
            }
            .item-card:hover { transform: translateY(-3px); }
            .item-card h4 { margin-bottom: 10px; color: #2c3e50; }

            .order-card, .returnable-card {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 15px;
                background: white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                transition: transform 0.3s ease;
            }
            .order-card:hover, .returnable-card:hover { transform: translateY(-2px); }

            .returnable-card { border-color: #f39c12; background: #fff8e1; }
            .overdue-card { border-color: #e74c3c; background: #ffebee; }

            .hidden { display: none !important; }
            .user-info { float: right; color: white; }
            .modal { 
                position: fixed; 
                top: 0; 
                left: 0; 
                width: 100%; 
                height: 100%; 
                background: rgba(0,0,0,0.5); 
                z-index: 1000; 
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .modal-content { 
                background: white; 
                padding: 20px; 
                border-radius: 8px; 
                max-width: 90%; 
                max-height: 90%; 
                overflow: auto; 
                position: relative;
            }
            .close { 
                position: absolute;
                top: 10px;
                right: 15px;
                font-size: 28px; 
                font-weight: bold; 
                cursor: pointer; 
                color: #aaa;
            }
            .close:hover { color: #000; }

            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f8f9fa; font-weight: bold; }
            tr:hover { background-color: #f5f5f5; }

            .low-stock { background-color: #ffebee; border-left: 4px solid #f44336; }
            .in-stock { background-color: #e8f5e8; border-left: 4px solid #4caf50; }
            .has-returnable { background-color: #fff3e0; border-left: 4px solid #ff9800; }

            .status-pending { color: #f39c12; font-weight: bold; }
            .status-confirmed { color: #27ae60; font-weight: bold; }
            .status-cancelled { color: #e74c3c; font-weight: bold; }
            .status-fulfilled { color: #3498db; font-weight: bold; }

            .alert { 
                padding: 12px; 
                margin: 10px 0; 
                border-radius: 4px; 
                font-weight: 500;
            }
            .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }

            /* Loading spinner */
            .loading {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #3498db;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            @media (max-width: 768px) {
                .nav-tabs { flex-direction: column; }
                .stats-grid { grid-template-columns: 1fr; }
                .item-grid { grid-template-columns: 1fr; }
                .container { padding: 10px; }
            }
        </style>
    </head>
    <body>
        <!-- Database Status Indicator -->
        <div id="database-status" class="status-indicator" onclick="showDatabaseDetails()">
            <span id="status-text">Checking...</span>
        </div>

        <!-- Login Screen -->
        <div id="login-screen">
            <div class="login-background"></div>
            <div class="login-container">
                <div class="digiassets-logo">
                    <h1>DigiAssets</h1>
                    <p>Complete Digital Inventory Management</p>
                </div>
                <form id="login-form">
                    <div class="form-group">
                        <label for="employee_id">Employee ID:</label>
                        <input type="text" id="employee_id" required value="ADMIN001">
                    </div>
                    <div class="form-group">
                        <label for="password">Password:</label>
                        <input type="password" id="password" required value="admin123">
                    </div>
                    <button type="submit" class="btn" style="width: 100%;">Login to DigiAssets</button>
                </form>
            </div>
        </div>

        <!-- Main Application -->
        <div id="main-app" class="hidden">
            <div class="header">
                <div class="container" style="display: flex; align-items: center;">
                    <div style="flex: 1;">
                        <h1>📦 DigiAssets - Complete Digital Inventory Management</h1>
                    </div>
                    <div class="user-info">
                        Welcome, <span id="user-name"></span> | 
                        <a href="#" onclick="logout()" style="color: white;">Logout</a>
                    </div>
                </div>
            </div>

            <div class="container">
                <div class="nav-tabs">
                    <button class="nav-tab active" onclick="switchTab('dashboard')">Dashboard</button>
                    <button class="nav-tab" onclick="switchTab('inventory')">Inventory</button>
                    <button class="nav-tab" onclick="switchTab('transactions')">Transactions</button>
                    <button class="nav-tab" onclick="switchTab('orders')">Orders</button>
                    <button class="nav-tab" onclick="switchTab('categories')">Categories</button>
                    <button class="nav-tab" onclick="switchTab('items')">Item Master</button>
                    <button class="nav-tab" onclick="switchTab('returnable')">Returnable</button>
                    <button class="nav-tab" id="admin-nav-tab" onclick="switchTab('admin')">Admin Panel</button>
                </div>

                <!-- Dashboard Tab -->
                <div id="dashboard-tab" class="content-area">
                    <h3>📊 Dashboard</h3>
                    <div id="dashboard-stats" class="stats-grid"></div>
                    
                    <h4 style="margin: 30px 0 15px 0; color: #e74c3c;">⚠️ Low Stock Items</h4>
                    <div id="low-stock-items"></div>
                </div>

                <!-- Orders Tab -->
                <div id="orders-tab" class="content-area hidden">
                    <h3>📋 Order Management</h3>
                    <div style="margin-bottom: 20px;">
                        <button class="btn btn-success" onclick="showAddOrderModal()">➕ Create Order</button>
                        <button class="btn" onclick="loadOrders()">🔄 Refresh</button>
                    </div>
                    <div style="margin-bottom: 20px;">
                        <select id="order-status-filter" onchange="filterOrders()">
                            <option value="">All Status</option>
                            <option value="PENDING">Pending</option>
                            <option value="PROCESSING">Processing</option>
                            <option value="FULFILLED">Fulfilled</option>
                            <option value="CANCELLED">Cancelled</option>
                        </select>
                    </div>
                    <div id="orders-list"></div>
                </div>

                <!-- Categories Tab -->
                <div id="categories-tab" class="content-area hidden">
                    <h3>🏷️ Category Management</h3>
                    <div style="margin-bottom: 20px;">
                        <button class="btn btn-success" onclick="showAddCategoryModal()">➕ Add Category</button>
                        <button class="btn" onclick="loadCategories()">🔄 Refresh</button>
                    </div>
                    <div id="categories-list"></div>
                </div>

                <!-- Items Tab -->
                <div id="items-tab" class="content-area hidden">
                    <h3>📋 Item Master Management</h3>
                    <div style="margin-bottom: 20px;">
                        <button class="btn btn-success" onclick="showAddItemModal()">➕ Add Item</button>
                        <button class="btn" onclick="loadItems()">🔄 Refresh</button>
                    </div>
                    <div style="margin-bottom: 20px;">
                        <select id="category-filter" onchange="filterItems()">
                            <option value="">All Categories</option>
                        </select>
                    </div>
                    <div id="items-list" class="item-grid"></div>
                </div>

                <!-- Inventory Tab -->
                <div id="inventory-tab" class="content-area hidden">
                    <h3>📦 Inventory Management</h3>
                    <div style="margin-bottom: 20px;">
                        <button class="btn btn-success" onclick="showStockInModal()">📈 Stock In</button>
                        <button class="btn btn-warning" onclick="showStockOutModal()">📉 Stock Out</button>
                        <button class="btn btn-purple" onclick="showOrderFulfillmentModal()">📋 Order Fulfillment</button>
                        <button class="btn btn-info" onclick="showStockAdjustModal()">⚖️ Stock Adjust</button>
                        <button class="btn" onclick="loadInventory()">🔄 Refresh</button>
                    </div>
                    <div id="inventory-list" class="item-grid"></div>
                </div>

                <!-- Transactions Tab -->
                <div id="transactions-tab" class="content-area hidden">
                    <h3>📜 Transaction History</h3>
                    <div style="margin-bottom: 20px;">
                        <select id="transaction-type-filter" onchange="filterTransactions()">
                            <option value="">All Types</option>
                            <option value="IN">Stock In</option>
                            <option value="OUT">Stock Out</option>
                            <option value="ADJUST">Adjustments</option>
                        </select>
                        <select id="transaction-status-filter" onchange="filterTransactions()">
                            <option value="">All Status</option>
                            <option value="PENDING">Pending</option>
                            <option value="CONFIRMED">Confirmed</option>
                            <option value="CANCELLED">Cancelled</option>
                        </select>
                        <button class="btn" onclick="loadTransactions()">🔄 Refresh</button>
                    </div>
                    <div id="transactions-list"></div>
                </div>

                <!-- Returnable Items Tab -->
                <div id="returnable-tab" class="content-area hidden">
                    <h3>🔄 Returnable Items Management</h3>
                    <div style="margin-bottom: 20px;">
                        <button class="btn" onclick="loadReturnableItems()">🔄 Refresh</button>
                    </div>
                    <div id="returnable-items-list"></div>
                </div>

                <!-- Admin Panel -->
                <div id="admin-tab" class="content-area hidden">
                    <h3>⚙️ Admin Panel</h3>
                    <div class="nav-tabs" style="margin-top: 20px;">
                        <button class="nav-tab active" onclick="switchAdminTab('users')">User Management</button>
                        <button class="nav-tab" onclick="switchAdminTab('departments')">Departments</button>
                        <button class="nav-tab" onclick="switchAdminTab('divisions')">Divisions</button>
                    </div>
                    
                    <div id="admin-users" class="content-area" style="margin-top: 20px;">
                        <h4>👥 User Management</h4>
                        <div style="margin-bottom: 20px;">
                            <button class="btn btn-success" onclick="showAddUserModal()">➕ Add User</button>
                        </div>
                        <div id="users-list"></div>
                    </div>
                    
                    <div id="admin-departments" class="content-area hidden" style="margin-top: 20px;">
                        <h4>🏛️ Department Management</h4>
                        <div style="margin-bottom: 20px;">
                            <button class="btn btn-success" onclick="showAddDepartmentModal()">➕ Add Department</button>
                        </div>
                        <div id="departments-list"></div>
                    </div>
                    
                    <div id="admin-divisions" class="content-area hidden" style="margin-top: 20px;">
                        <h4>🏢 Division Management</h4>
                        <div style="margin-bottom: 20px;">
                            <button class="btn btn-success" onclick="showAddDivisionModal()">➕ Add Division</button>
                        </div>
                        <div id="divisions-list"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- All Modals -->
        <div id="add-order-modal" class="modal hidden">
            <div class="modal-content">
                <span class="close" onclick="closeAddOrderModal()">&times;</span>
                <h3>Create New Order</h3>
                <form id="add-order-form">
                    <div class="form-group">
                        <label for="order-customer-name">Customer Name:</label>
                        <input type="text" id="order-customer-name" required>
                    </div>
                    <div class="form-group">
                        <label for="order-customer-contact">Customer Contact:</label>
                        <input type="text" id="order-customer-contact" required>
                    </div>
                    <div class="form-group">
                        <label for="order-delivery-date">Expected Delivery Date:</label>
                        <input type="date" id="order-delivery-date">
                    </div>
                    <div class="form-group">
                        <label for="order-notes">Notes:</label>
                        <textarea id="order-notes"></textarea>
                    </div>
                    <button type="submit" class="btn">Create Order</button>
                </form>
            </div>
        </div>

        <div id="add-category-modal" class="modal hidden">
            <div class="modal-content">
                <span class="close" onclick="closeAddCategoryModal()">&times;</span>
                <h3>Add New Category</h3>
                <form id="add-category-form">
                    <div class="form-group">
                        <label for="category-name">Category Name:</label>
                        <input type="text" id="category-name" required>
                    </div>
                    <div class="form-group">
                        <label for="category-description">Description:</label>
                        <textarea id="category-description"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="parent-category">Parent Category:</label>
                        <select id="parent-category">
                            <option value="">None (Root Category)</option>
                        </select>
                    </div>
                    <button type="submit" class="btn">Add Category</button>
                </form>
            </div>
        </div>

        <div id="add-item-modal" class="modal hidden">
            <div class="modal-content" style="max-width: 600px;">
                <span class="close" onclick="closeAddItemModal()">&times;</span>
                <h3>Add New Item</h3>
                <form id="add-item-form">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        <div class="form-group">
                            <label for="item-code">Item Code:</label>
                            <input type="text" id="item-code" required>
                        </div>
                        <div class="form-group">
                            <label for="item-name">Item Name:</label>
                            <input type="text" id="item-name" required>
                        </div>
                        <div class="form-group">
                            <label for="item-category">Category:</label>
                            <select id="item-category" required>
                                <option value="">Select Category</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="item-uom">Unit of Measure:</label>
                            <select id="item-uom" required>
                                <option value="PCS">Pieces</option>
                                <option value="KG">Kilograms</option>
                                <option value="LTR">Liters</option>
                                <option value="MTR">Meters</option>
                                <option value="BOX">Box</option>
                                <option value="SET">Set</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="item-min-stock">Min Stock Level:</label>
                            <input type="number" id="item-min-stock" step="0.001" value="0">
                        </div>
                        <div class="form-group">
                            <label for="item-max-stock">Max Stock Level:</label>
                            <input type="number" id="item-max-stock" step="0.001" value="0">
                        </div>
                        <div class="form-group">
                            <label for="item-cost">Standard Cost:</label>
                            <input type="number" id="item-cost" step="0.01" value="0">
                        </div>
                        <div class="form-group">
                            <label for="item-location">Location:</label>
                            <input type="text" id="item-location">
                        </div>
                        <div class="form-group">
                            <label for="item-manufacturer">Manufacturer:</label>
                            <input type="text" id="item-manufacturer">
                        </div>
                        <div class="form-group">
                            <label for="item-model">Model Number:</label>
                            <input type="text" id="item-model">
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="item-description">Description:</label>
                        <textarea id="item-description"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="item-specifications">Specifications:</label>
                        <textarea id="item-specifications"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="item-warranty">Warranty (months):</label>
                        <input type="number" id="item-warranty" value="0">
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="item-is-returnable"> Item is Returnable
                        </label>
                    </div>
                    <button type="submit" class="btn">Add Item</button>
                </form>
            </div>
        </div>

        <div id="stock-transaction-modal" class="modal hidden">
            <div class="modal-content">
                <span class="close" onclick="closeStockTransactionModal()">&times;</span>
                <h3 id="transaction-modal-title">Stock Transaction</h3>
                <form id="stock-transaction-form">
                    <input type="hidden" id="transaction-type">
                    <div class="form-group">
                        <label for="transaction-item">Item:</label>
                        <select id="transaction-item" required>
                            <option value="">Select Item</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="transaction-subtype">Sub Type:</label>
                        <select id="transaction-subtype" required>
                            <option value="">Select Sub Type</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="transaction-quantity">Quantity:</label>
                        <input type="number" id="transaction-quantity" step="0.001" required>
                    </div>
                    <div class="form-group" id="returnable-quantity-group" style="display: none;">
                        <label for="transaction-returnable-quantity">Returnable Quantity:</label>
                        <input type="number" id="transaction-returnable-quantity" step="0.001" value="0">
                    </div>
                    <div class="form-group">
                        <label for="transaction-cost">Unit Cost:</label>
                        <input type="number" id="transaction-cost" step="0.01" value="0">
                    </div>
                    <div class="form-group">
                        <label for="transaction-reference">Reference Number:</label>
                        <input type="text" id="transaction-reference">
                    </div>
                    <div class="form-group">
                        <label for="transaction-vendor">Vendor/Customer:</label>
                        <input type="text" id="transaction-vendor">
                    </div>
                    <div class="form-group" id="expected-return-date-group" style="display: none;">
                        <label for="transaction-expected-return">Expected Return Date:</label>
                        <input type="date" id="transaction-expected-return">
                    </div>
                    <div class="form-group">
                        <label for="transaction-remarks">Remarks:</label>
                        <textarea id="transaction-remarks"></textarea>
                    </div>
                    <button type="submit" class="btn">Create Transaction</button>
                </form>
            </div>
        </div>

        <div id="add-user-modal" class="modal hidden">
            <div class="modal-content">
                <span class="close" onclick="closeAddUserModal()">&times;</span>
                <h3>Add New User</h3>
                <form id="add-user-form">
                    <div class="form-group">
                        <label for="user-employee-id">Employee ID:</label>
                        <input type="text" id="user-employee-id" required>
                    </div>
                    <div class="form-group">
                        <label for="user-name">Name:</label>
                        <input type="text" id="user-name" required>
                    </div>
                    <div class="form-group">
                        <label for="user-email">Email:</label>
                        <input type="email" id="user-email" required>
                    </div>
                    <div class="form-group">
                        <label for="user-password">Password:</label>
                        <input type="password" id="user-password" required>
                    </div>
                    <div class="form-group">
                        <label for="user-department">Department:</label>
                        <select id="user-department" required>
                            <option value="">Select Department</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="user-is-admin"> Admin User
                        </label>
                    </div>
                    <button type="submit" class="btn">Add User</button>
                </form>
            </div>
        </div>

        <div id="add-department-modal" class="modal hidden">
            <div class="modal-content">
                <span class="close" onclick="closeAddDepartmentModal()">&times;</span>
                <h3>Add New Department</h3>
                <form id="add-department-form">
                    <div class="form-group">
                        <label for="dept-name">Department Name:</label>
                        <input type="text" id="dept-name" required>
                    </div>
                    <div class="form-group">
                        <label for="dept-description">Description:</label>
                        <textarea id="dept-description"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="dept-division">Division:</label>
                        <select id="dept-division" required>
                            <option value="">Select Division</option>
                        </select>
                    </div>
                    <button type="submit" class="btn">Add Department</button>
                </form>
            </div>
        </div>

        <div id="add-division-modal" class="modal hidden">
            <div class="modal-content">
                <span class="close" onclick="closeAddDivisionModal()">&times;</span>
                <h3>Add New Division</h3>
                <form id="add-division-form">
                    <div class="form-group">
                        <label for="div-name">Division Name:</label>
                        <input type="text" id="div-name" required>
                    </div>
                    <div class="form-group">
                        <label for="div-description">Description:</label>
                        <textarea id="div-description"></textarea>
                    </div>
                    <button type="submit" class="btn">Add Division</button>
                </form>
            </div>
        </div>

        <script>
            // Global variables
            let currentUser = null;
            let allCategories = [];
            let allItems = [];
            let allTransactions = [];
            let allOrders = [];
            let allReturnableItems = [];
            let databaseStatus = null;
            
            // ============================
            // DATABASE STATUS MONITORING
            // ============================
            
            async function checkDatabaseStatus() {
                try {
                    const response = await fetch('/api/database-status');
                    const status = await response.json();
                    databaseStatus = status;
                    
                    const statusElement = document.getElementById('database-status');
                    const statusText = document.getElementById('status-text');
                    
                    if (status.status === 'healthy') {
                        statusElement.className = 'status-indicator status-healthy';
                        statusText.textContent = '✅ Database OK';
                    } else if (status.status === 'needs_migration') {
                        statusElement.className = 'status-indicator status-warning';
                        statusText.textContent = '⚠️ DB Migration Needed';
                    } else {
                        statusElement.className = 'status-indicator status-error';
                        statusText.textContent = '❌ Database Error';
                    }
                    
                } catch (error) {
                    const statusElement = document.getElementById('database-status');
                    const statusText = document.getElementById('status-text');
                    statusElement.className = 'status-indicator status-error';
                    statusText.textContent = '❌ Connection Error';
                }
            }
            
            function showDatabaseDetails() {
                if (!databaseStatus) return;
                
                const modal = document.createElement('div');
                modal.className = 'modal';
                modal.innerHTML = `
                    <div class="modal-content">
                        <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
                        <h3>📊 Database Status</h3>
                        <div style="margin: 20px 0;">
                            <p><strong>Status:</strong> ${databaseStatus.status}</p>
                            <p><strong>Existing Tables:</strong> ${databaseStatus.existing_tables}</p>
                            <p><strong>Expected Tables:</strong> ${databaseStatus.expected_tables}</p>
                            <p><strong>Last Check:</strong> ${new Date(databaseStatus.last_check).toLocaleString()}</p>
                            ${databaseStatus.missing_tables && databaseStatus.missing_tables.length > 0 ? 
                                `<p><strong>Missing Tables:</strong> ${databaseStatus.missing_tables.join(', ')}</p>` : ''}
                            ${databaseStatus.missing_columns && databaseStatus.missing_columns.length > 0 ? 
                                `<p><strong>Missing Columns:</strong><br>${databaseStatus.missing_columns.join('<br>')}</p>` : ''}
                            ${databaseStatus.error ? `<p><strong>Error:</strong> ${databaseStatus.error}</p>` : ''}
                        </div>
                        <div style="text-align: center;">
                            <button class="btn" onclick="checkDatabaseStatus(); this.closest('.modal').remove()">🔄 Refresh Status</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
            }
            
            // Check database status every 30 seconds
            setInterval(checkDatabaseStatus, 30000);
            checkDatabaseStatus();
            
            // ============================
            // API UTILITY FUNCTIONS
            // ============================
            
            async function apiCall(endpoint, options = {}) {
                try {
                    const response = await fetch(endpoint, {
                        credentials: 'include',
                        ...options
                    });
                    if (!response.ok) {
                        const error = await response.text();
                        throw new Error(error);
                    }
                    return response.json();
                } catch (error) {
                    console.error('API call error:', error);
                    throw error;
                }
            }

            function showAlert(message, type = 'success') {
                const alertDiv = document.createElement('div');
                alertDiv.className = `alert alert-${type}`;
                alertDiv.textContent = message;
                alertDiv.style.position = 'fixed';
                alertDiv.style.top = '70px';
                alertDiv.style.right = '20px';
                alertDiv.style.zIndex = '9999';
                alertDiv.style.maxWidth = '300px';
                
                document.body.appendChild(alertDiv);
                
                setTimeout(() => {
                    alertDiv.remove();
                }, 3000);
            }

            // ============================
            // AUTHENTICATION
            // ============================
            
            document.getElementById('login-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                try {
                    const formData = new FormData();
                    formData.append('employee_id', document.getElementById('employee_id').value);
                    formData.append('password', document.getElementById('password').value);

                    const response = await fetch('/login', {
                        method: 'POST',
                        credentials: 'include',
                        body: formData
                    });

                    if (response.ok) {
                        const user = await response.json();
                        currentUser = user;
                        showMainApp();
                        showAlert('Login successful!', 'success');
                    } else {
                        showAlert('Invalid credentials', 'error');
                    }
                } catch (error) {
                    console.error('Login error:', error);
                    showAlert('Login failed: ' + error.message, 'error');
                }
            });

            function showMainApp() {
                document.getElementById('login-screen').classList.add('hidden');
                document.getElementById('main-app').classList.remove('hidden');
                document.getElementById('user-name').textContent = currentUser.name;
                
                if (currentUser.is_admin) {
                    document.getElementById('admin-nav-tab').style.display = 'block';
                } else {
                    document.getElementById('admin-nav-tab').style.display = 'none';
                }
                
                loadDashboard();
            }

            function logout() {
                fetch('/logout', {
                    method: 'POST',
                    credentials: 'include'
                }).then(() => {
                    location.reload();
                });
            }

            // ============================
            // NAVIGATION
            // ============================

            function switchTab(tabName) {
                // Hide all tabs
                const tabs = ['dashboard', 'orders', 'categories', 'items', 'inventory', 'transactions', 'returnable', 'admin'];
                tabs.forEach(tab => {
                    const element = document.getElementById(tab + '-tab');
                    if (element) {
                        element.classList.add('hidden');
                    }
                });
                
                // Show target tab
                const targetTab = document.getElementById(tabName + '-tab');
                if (targetTab) {
                    targetTab.classList.remove('hidden');
                }
                
                // Update navigation
                const navTabs = document.querySelectorAll('.container > .nav-tabs .nav-tab');
                navTabs.forEach(tab => tab.classList.remove('active'));
                if (event?.target) {
                    event.target.classList.add('active');
                }

                // Load content based on tab
                switch(tabName) {
                    case 'dashboard':
                        loadDashboard();
                        break;
                    case 'orders':
                        loadOrders();
                        break;
                    case 'categories':
                        loadCategories();
                        break;
                    case 'items':
                        loadItems();
                        loadCategoriesForDropdown();
                        break;
                    case 'inventory':
                        loadInventory();
                        break;
                    case 'transactions':
                        loadTransactions();
                        break;
                    case 'returnable':
                        loadReturnableItems();
                        break;
                    case 'admin':
                        loadUsers();
                        break;
                }
            }

            function switchAdminTab(tabName) {
                const adminTabs = ['users', 'departments', 'divisions'];
                adminTabs.forEach(tab => {
                    const element = document.getElementById('admin-' + tab);
                    if (element) {
                        element.classList.add('hidden');
                    }
                });
                
                const targetTab = document.getElementById('admin-' + tabName);
                if (targetTab) {
                    targetTab.classList.remove('hidden');
                }
                
                const adminNavTabs = document.querySelectorAll('#admin-tab .nav-tabs .nav-tab');
                adminNavTabs.forEach(tab => tab.classList.remove('active'));
                if (event?.target) event.target.classList.add('active');
                
                switch(tabName) {
                    case 'users':
                        loadUsers();
                        break;
                    case 'departments':
                        loadDepartments();
                        break;
                    case 'divisions':
                        loadDivisions();
                        break;
                }
            }

            // ============================
            // DASHBOARD FUNCTIONS
            // ============================

            async function loadDashboard() {
                try {
                    const stats = await apiCall('/dashboard/stats');
                    const lowStockItems = await apiCall('/dashboard/low-stock');
                    
                    displayDashboardStats(stats);
                    displayLowStockItems(lowStockItems);
                } catch (error) {
                    console.error('Error loading dashboard:', error);
                    showAlert('Error loading dashboard', 'error');
                }
            }

            function displayDashboardStats(stats) {
                const container = document.getElementById('dashboard-stats');
                container.innerHTML = `
                    <div class="stat-card" style="background: linear-gradient(135deg, #3498db, #2980b9);">
                        <h3>${stats.total_categories}</h3>
                        <p>Total Categories</p>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #27ae60, #229954);">
                        <h3>${stats.total_items}</h3>
                        <p>Total Items</p>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #f39c12, #e67e22);">
                        <h3>${stats.total_transactions}</h3>
                        <p>Total Transactions</p>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #e74c3c, #c0392b);">
                        <h3>${stats.pending_transactions}</h3>
                        <p>Pending Transactions</p>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #9b59b6, #8e44ad);">
                        <h3>${stats.low_stock_items}</h3>
                        <p>Low Stock Items</p>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #16a085, #138d75);">
                        <h3>${stats.total_orders}</h3>
                        <p>Total Orders</p>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #d35400, #ba4a00);">
                        <h3>${stats.pending_orders}</h3>
                        <p>Pending Orders</p>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #f39c12, #e67e22);">
                        <h3>${stats.returnable_items}</h3>
                        <p>Returnable Items</p>
                    </div>
                `;
            }

            function displayLowStockItems(items) {
                const container = document.getElementById('low-stock-items');
                
                if (items.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #27ae60; padding: 20px;">✅ All items are adequately stocked!</p>';
                    return;
                }
                
                container.innerHTML = items.map(item => `
                    <div class="item-card low-stock">
                        <h4>⚠️ ${item.item_code} - ${item.item_name}</h4>
                        <p><strong>Category:</strong> ${item.category?.name || 'N/A'}</p>
                        <p><strong>Current Stock:</strong> ${item.current_stock}</p>
                        <p><strong>Min Level:</strong> ${item.min_stock_level}</p>
                        <div style="margin-top: 10px;">
                            <button class="btn btn-success" onclick="stockInItem(${item.id})">📈 Stock In</button>
                        </div>
                    </div>
                `).join('');
            }

            // ============================
            // ORDER MANAGEMENT FUNCTIONS
            // ============================

            async function loadOrders() {
                try {
                    allOrders = await apiCall('/orders');
                    displayOrders();
                } catch (error) {
                    console.error('Error loading orders:', error);
                    showAlert('Error loading orders', 'error');
                }
            }

            function displayOrders() {
                const container = document.getElementById('orders-list');
                
                if (allOrders.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #666; padding: 40px;">No orders found.</p>';
                    return;
                }
                
                container.innerHTML = allOrders.map(order => `
                    <div class="order-card">
                        <h4>📋 ${order.order_number}</h4>
                        <p><strong>Customer:</strong> ${order.customer_name}</p>
                        <p><strong>Contact:</strong> ${order.customer_contact}</p>
                        <p><strong>Order Date:</strong> ${new Date(order.order_date).toLocaleDateString()}</p>
                        <p><strong>Expected Delivery:</strong> ${order.expected_delivery_date ? new Date(order.expected_delivery_date).toLocaleDateString() : 'Not specified'}</p>
                        <p><strong>Status:</strong> <span class="status-${order.order_status.toLowerCase()}">${order.order_status}</span></p>
                        <p><strong>Total Amount:</strong> ${order.total_amount}</p>
                        <p><strong>Items:</strong> ${order.item_count}</p>
                        <p><strong>Notes:</strong> ${order.notes || 'None'}</p>
                        <div style="margin-top: 10px;">
                            <button class="btn btn-info" onclick="viewOrderDetails(${order.id})">👁️ View Details</button>
                            ${order.order_status === 'PENDING' ? `
                                <button class="btn btn-success" onclick="addOrderItem(${order.id})">➕ Add Item</button>
                                <button class="btn btn-warning" onclick="fulfillOrder(${order.id})">✅ Fulfill Order</button>
                            ` : ''}
                            ${(order.order_status === 'PENDING' || order.order_status === 'CANCELLED') ? `
                                <button class="btn btn-danger" onclick="deleteOrder(${order.id}, '${order.order_number}')">🗑️ Delete</button>
                            ` : ''}
                        </div>
                    </div>
                `).join('');
            }

            function filterOrders() {
                const statusFilter = document.getElementById('order-status-filter').value;
                
                let filteredOrders = allOrders;
                
                if (statusFilter) {
                    filteredOrders = filteredOrders.filter(order => order.order_status === statusFilter);
                }
                
                const container = document.getElementById('orders-list');
                
                if (filteredOrders.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #666; padding: 40px;">No orders found matching the filters.</p>';
                    return;
                }
                
                container.innerHTML = filteredOrders.map(order => `
                    <div class="order-card">
                        <h4>📋 ${order.order_number}</h4>
                        <p><strong>Customer:</strong> ${order.customer_name}</p>
                        <p><strong>Contact:</strong> ${order.customer_contact}</p>
                        <p><strong>Order Date:</strong> ${new Date(order.order_date).toLocaleDateString()}</p>
                        <p><strong>Expected Delivery:</strong> ${order.expected_delivery_date ? new Date(order.expected_delivery_date).toLocaleDateString() : 'Not specified'}</p>
                        <p><strong>Status:</strong> <span class="status-${order.order_status.toLowerCase()}">${order.order_status}</span></p>
                        <p><strong>Total Amount:</strong> ${order.total_amount}</p>
                        <p><strong>Items:</strong> ${order.item_count}</p>
                        <p><strong>Notes:</strong> ${order.notes || 'None'}</p>
                        <div style="margin-top: 10px;">
                            <button class="btn btn-info" onclick="viewOrderDetails(${order.id})">👁️ View Details</button>
                            ${order.order_status === 'PENDING' ? `
                                <button class="btn btn-success" onclick="addOrderItem(${order.id})">➕ Add Item</button>
                                <button class="btn btn-warning" onclick="fulfillOrder(${order.id})">✅ Fulfill Order</button>
                            ` : ''}
                            ${(order.order_status === 'PENDING' || order.order_status === 'CANCELLED') ? `
                                <button class="btn btn-danger" onclick="deleteOrder(${order.id}, '${order.order_number}')">🗑️ Delete</button>
                            ` : ''}
                        </div>
                    </div>
                `).join('');
            }

            function showAddOrderModal() {
                document.getElementById('add-order-modal').classList.remove('hidden');
            }

            function closeAddOrderModal() {
                document.getElementById('add-order-modal').classList.add('hidden');
                document.getElementById('add-order-form').reset();
            }

            document.getElementById('add-order-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData();
                formData.append('customer_name', document.getElementById('order-customer-name').value);
                formData.append('customer_contact', document.getElementById('order-customer-contact').value);
                formData.append('expected_delivery_date', document.getElementById('order-delivery-date').value);
                formData.append('notes', document.getElementById('order-notes').value);

                try {
                    await fetch('/orders', {
                        method: 'POST',
                        credentials: 'include',
                        body: formData
                    });
                    
                    showAlert('Order created successfully!', 'success');
                    closeAddOrderModal();
                    loadOrders();
                } catch (error) {
                    showAlert('Error creating order: ' + error.message, 'error');
                }
            });



            // Add this JavaScript code to your existing script section in digiassets.py
// Insert this after your existing JavaScript functions

// ============================
// ADD ITEM TO ORDER FUNCTIONALITY
// ============================

async function addOrderItem(orderId) {
    try {
        // Load available items
        const items = await apiCall('/items');
        
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
                <h3>➕ Add Item to Order</h3>
                <form id="add-order-item-form">
                    <div class="form-group">
                        <label for="order-item-select">Select Item:</label>
                        <select id="order-item-select" required onchange="updateItemInfo()">
                            <option value="">Choose an item...</option>
                            ${items.map(item => `
                                <option value="${item.id}" 
                                        data-cost="${item.standard_cost}" 
                                        data-uom="${item.unit_of_measure}"
                                        data-stock="${item.current_stock}">
                                    ${item.item_code} - ${item.item_name} (Stock: ${item.current_stock} ${item.unit_of_measure})
                                </option>
                            `).join('')}
                        </select>
                    </div>
                    
                    <div id="item-info" class="form-group" style="display: none; background: #f8f9fa; padding: 10px; border-radius: 4px; margin: 10px 0;">
                        <p><strong>Current Stock:</strong> <span id="current-stock">0</span> <span id="item-uom">PCS</span></p>
                        <p><strong>Standard Cost:</strong> $<span id="standard-cost">0.00</span></p>
                    </div>
                    
                    <div class="form-group">
                        <label for="order-item-quantity">Quantity:</label>
                        <input type="number" id="order-item-quantity" step="0.001" min="0.001" required onchange="calculateTotal()">
                        <small id="quantity-warning" style="color: #e74c3c; display: none;"></small>
                    </div>
                    
                    <div class="form-group">
                        <label for="order-item-price">Unit Price ($):</label>
                        <input type="number" id="order-item-price" step="0.01" min="0" required onchange="calculateTotal()">
                    </div>
                    
                    <div class="form-group">
                        <label>Total Price:</label>
                        <div style="font-size: 1.2em; font-weight: bold; color: #2c3e50;">
                            $<span id="total-price">0.00</span>
                        </div>
                    </div>
                    
                    <div style="text-align: center; margin-top: 20px;">
                        <button type="submit" class="btn btn-success">➕ Add Item to Order</button>
                        <button type="button" class="btn" onclick="this.closest('.modal').remove()">Cancel</button>
                    </div>
                </form>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Store order ID for form submission
        window.currentOrderId = orderId;
        
        // Add event listener for the form
        document.getElementById('add-order-item-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await handleAddOrderItem();
        });
        
    } catch (error) {
        showAlert('Error loading items: ' + error.message, 'error');
    }
}

function updateItemInfo() {
    const select = document.getElementById('order-item-select');
    const selectedOption = select.options[select.selectedIndex];
    const infoDiv = document.getElementById('item-info');
    
    if (selectedOption.value) {
        const stock = selectedOption.dataset.stock;
        const cost = selectedOption.dataset.cost;
        const uom = selectedOption.dataset.uom;
        
        document.getElementById('current-stock').textContent = stock;
        document.getElementById('item-uom').textContent = uom;
        document.getElementById('standard-cost').textContent = parseFloat(cost).toFixed(2);
        document.getElementById('order-item-price').value = cost;
        
        infoDiv.style.display = 'block';
        calculateTotal();
    } else {
        infoDiv.style.display = 'none';
    }
}

function calculateTotal() {
    const quantity = parseFloat(document.getElementById('order-item-quantity').value) || 0;
    const price = parseFloat(document.getElementById('order-item-price').value) || 0;
    const total = quantity * price;
    
    document.getElementById('total-price').textContent = total.toFixed(2);
    
    // Check stock availability
    const select = document.getElementById('order-item-select');
    const selectedOption = select.options[select.selectedIndex];
    const warning = document.getElementById('quantity-warning');
    
    if (selectedOption.value) {
        const stock = parseFloat(selectedOption.dataset.stock);
        if (quantity > stock) {
            warning.textContent = `⚠️ Requested quantity (${quantity}) exceeds available stock (${stock})`;
            warning.style.display = 'block';
        } else {
            warning.style.display = 'none';
        }
    }
}

async function handleAddOrderItem() {
    const orderId = window.currentOrderId;
    
    if (!orderId) {
        showAlert('Order ID not found', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('item_master_id', document.getElementById('order-item-select').value);
    formData.append('requested_quantity', document.getElementById('order-item-quantity').value);
    formData.append('unit_price', document.getElementById('order-item-price').value);
    
    try {
        const response = await fetch(`/orders/${orderId}/items`, {
            method: 'POST',
            credentials: 'include',
            body: formData
        });
        
        if (response.ok) {
            showAlert('Item added to order successfully!', 'success');
            
            // Close modal
            document.querySelector('.modal').remove();
            
            // Refresh orders list
            await loadOrders();
            
        } else {
            const errorText = await response.text();
            throw new Error(errorText);
        }
    } catch (error) {
        showAlert('Error adding item to order: ' + error.message, 'error');
    }
}

// ============================
// FULFILL ORDER FUNCTIONALITY
// ============================

async function fulfillOrder(orderId) {
    try {
        // Get order details first
        const order = await apiCall(`/orders/${orderId}`);
        
        if (order.order_status !== 'PENDING') {
            showAlert('Only pending orders can be fulfilled', 'warning');
            return;
        }
        
        if (!order.order_items || order.order_items.length === 0) {
            showAlert('Order has no items to fulfill', 'warning');
            return;
        }
        
        // Check stock availability for all items
        let stockIssues = [];
        let canFulfillAll = true;
        
        // Get current items with stock info
        const allItems = await apiCall('/items');
        
        for (const orderItem of order.order_items) {
            const remainingQty = orderItem.requested_quantity - orderItem.fulfilled_quantity;
            if (remainingQty > 0) {
                // Find current stock for this item
                const itemStock = allItems.find(i => i.id === orderItem.item.id);
                
                if (!itemStock || itemStock.current_stock < remainingQty) {
                    stockIssues.push({
                        item_code: orderItem.item.item_code,
                        item_name: orderItem.item.item_name,
                        needed: remainingQty,
                        available: itemStock ? itemStock.current_stock : 0
                    });
                    canFulfillAll = false;
                }
            }
        }
        
        // Show fulfillment modal
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 800px;">
                <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
                <h3>✅ Fulfill Order: ${order.order_number}</h3>
                
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <h4>Order Details</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        <div>
                            <p><strong>Customer:</strong> ${order.customer_name}</p>
                            <p><strong>Contact:</strong> ${order.customer_contact}</p>
                        </div>
                        <div>
                            <p><strong>Order Date:</strong> ${new Date(order.order_date).toLocaleDateString()}</p>
                            <p><strong>Total Amount:</strong> $${order.total_amount}</p>
                        </div>
                    </div>
                </div>
                
                ${stockIssues.length > 0 ? `
                    <div style="background: #ffebee; border: 1px solid #f44336; padding: 15px; border-radius: 8px; margin: 15px 0;">
                        <h4 style="color: #f44336; margin-top: 0;">⚠️ Stock Issues</h4>
                        <p>The following items have insufficient stock:</p>
                        <ul>
                            ${stockIssues.map(issue => `
                                <li><strong>${issue.item_code}</strong>: Need ${issue.needed}, Available ${issue.available}</li>
                            `).join('')}
                        </ul>
                    </div>
                ` : ''}
                
                <div style="margin: 20px 0;">
                    <h4>Order Items</h4>
                    <table style="width: 100%; margin-top: 10px;">
                        <thead>
                            <tr>
                                <th style="text-align: left;">Item</th>
                                <th>Requested</th>
                                <th>Fulfilled</th>
                                <th>Remaining</th>
                                <th>Status</th>
                                <th style="text-align: center;">Fulfillment</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${order.order_items.map(item => {
                                const remainingQty = item.requested_quantity - item.fulfilled_quantity;
                                const stockItem = stockIssues.find(si => si.item_code === item.item.item_code);
                                const hasStock = !stockItem;
                                
                                return `
                                    <tr>
                                        <td>
                                            <strong>${item.item.item_code}</strong><br>
                                            ${item.item.item_name}
                                            ${item.item.is_returnable ? '<br><small style="color: #f39c12;">📦 Returnable</small>' : ''}
                                        </td>
                                        <td>${item.requested_quantity}</td>
                                        <td>${item.fulfilled_quantity}</td>
                                        <td style="font-weight: bold; color: ${remainingQty > 0 ? '#e74c3c' : '#27ae60'};">
                                            ${remainingQty}
                                        </td>
                                        <td><span class="status-${item.status.toLowerCase()}">${item.status}</span></td>
                                        <td style="text-align: center;">
                                            ${remainingQty > 0 ? 
                                                (hasStock ? 
                                                    `<input type="checkbox" id="fulfill-item-${item.id}" ${canFulfillAll ? 'checked' : ''}>` :
                                                    '<span style="color: #f44336;">❌ No Stock</span>'
                                                ) : 
                                                '<span style="color: #27ae60;">✅ Complete</span>'
                                            }
                                        </td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
                
                <div style="text-align: center; margin-top: 20px;">
                    ${canFulfillAll ? `
                        <button class="btn btn-success" onclick="processBulkFulfillment(${orderId})">
                            ✅ Fulfill Entire Order
                        </button>
                    ` : ''}
                    <button class="btn btn-info" onclick="processPartialFulfillment(${orderId})">
                        📦 Fulfill Selected Items
                    </button>
                    <button class="btn" onclick="this.closest('.modal').remove()">Cancel</button>
                </div>
                
                ${!canFulfillAll ? `
                    <div style="margin-top: 15px; padding: 10px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px;">
                        <small><strong>Note:</strong> Only items with sufficient stock can be fulfilled. You can fulfill available items now and complete the rest later when stock is replenished.</small>
                    </div>
                ` : ''}
            </div>
        `;
        
        document.body.appendChild(modal);
        
    } catch (error) {
        showAlert('Error loading order for fulfillment: ' + error.message, 'error');
    }
}

async function processBulkFulfillment(orderId) {
    const confirmed = confirm('Are you sure you want to fulfill the entire order? This will update inventory levels and cannot be easily undone.');
    
    if (!confirmed) return;
    
    try {
        const response = await fetch(`/orders/${orderId}/bulk-fulfill`, {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            const result = await response.json();
            showAlert(result.message, 'success');
            
            // Close modal and refresh
            document.querySelector('.modal').remove();
            await loadOrders();
            await loadDashboard();
            
        } else {
            const errorText = await response.text();
            throw new Error(errorText);
        }
    } catch (error) {
        showAlert('Error fulfilling order: ' + error.message, 'error');
    }
}

async function processPartialFulfillment(orderId) {
    // Get selected items
    const checkboxes = document.querySelectorAll('input[type="checkbox"][id^="fulfill-item-"]');
    const selectedItems = [];
    
    checkboxes.forEach(checkbox => {
        if (checkbox.checked) {
            const itemId = checkbox.id.replace('fulfill-item-', '');
            selectedItems.push(itemId);
        }
    });
    
    if (selectedItems.length === 0) {
        showAlert('Please select at least one item to fulfill', 'warning');
        return;
    }
    
    const confirmed = confirm(`Are you sure you want to fulfill ${selectedItems.length} selected item(s)?`);
    
    if (!confirmed) return;
    
    try {
        // Process each selected item
        let successCount = 0;
        let errorCount = 0;
        
        for (const itemId of selectedItems) {
            try {
                // Get order details to find the item
                const order = await apiCall(`/orders/${orderId}`);
                const orderItem = order.order_items.find(item => item.id == itemId);
                
                if (orderItem) {
                    const remainingQty = orderItem.requested_quantity - orderItem.fulfilled_quantity;
                    
                    if (remainingQty > 0) {
                        const formData = new FormData();
                        formData.append('order_item_id', itemId);
                        formData.append('fulfill_quantity', remainingQty);
                        formData.append('extra_quantity', '0');
                        formData.append('expected_return_date', '');
                        formData.append('remarks', 'Partial order fulfillment');
                        
                        const response = await fetch(`/orders/${orderId}/fulfill-item`, {
                            method: 'POST',
                            credentials: 'include',
                            body: formData
                        });
                        
                        if (response.ok) {
                            successCount++;
                        } else {
                            errorCount++;
                        }
                    }
                }
            } catch (error) {
                errorCount++;
            }
        }
        
        if (successCount > 0) {
            showAlert(`Successfully fulfilled ${successCount} item(s)${errorCount > 0 ? ` (${errorCount} failed)` : ''}`, 'success');
        } else {
            showAlert('No items were fulfilled', 'error');
        }
        
        // Close modal and refresh
        document.querySelector('.modal').remove();
        await loadOrders();
        await loadDashboard();
        
    } catch (error) {
        showAlert('Error processing partial fulfillment: ' + error.message, 'error');
    }
}

            async function deleteOrder(orderId, orderNumber) {
                const confirmed = confirm(
                    `Are you sure you want to delete order ${orderNumber}?\n\n` +
                    `This action cannot be undone!`
                );
                
                if (!confirmed) return;
                
                try {
                    const response = await fetch(`/orders/${orderId}`, {
                        method: 'DELETE',
                        credentials: 'include',
                    });
                    
                    if (response.ok) {
                        showAlert(`Order ${orderNumber} deleted successfully!`, 'success');
                        await loadOrders();
                        loadDashboard();
                    } else {
                        const errorText = await response.text();
                        throw new Error(errorText);
                    }
                } catch (error) {
                    console.error('Error deleting order:', error);
                    showAlert('Error deleting order: ' + error.message, 'error');
                }
            }

            async function viewOrderDetails(orderId) {
                try {
                    const order = await apiCall(`/orders/${orderId}`);
                    
                    let html = `
                        <div style="max-width: 800px;">
                            <h3>📋 Order Details: ${order.order_number}</h3>
                            <div style="margin: 20px 0;">
                                <p><strong>Customer:</strong> ${order.customer_name}</p>
                                <p><strong>Contact:</strong> ${order.customer_contact}</p>
                                <p><strong>Order Date:</strong> ${new Date(order.order_date).toLocaleDateString()}</p>
                                <p><strong>Expected Delivery:</strong> ${order.expected_delivery_date ? new Date(order.expected_delivery_date).toLocaleDateString() : 'Not specified'}</p>
                                <p><strong>Status:</strong> <span class="status-${order.order_status.toLowerCase()}">${order.order_status}</span></p>
                                <p><strong>Total Amount:</strong> ${order.total_amount}</p>
                                <p><strong>Notes:</strong> ${order.notes || 'None'}</p>
                            </div>
                            
                            <h4>Order Items:</h4>
                            <table style="margin-top: 20px;">
                                <thead>
                                    <tr>
                                        <th>Item</th>
                                        <th>Requested</th>
                                        <th>Fulfilled</th>
                                        <th>Returnable</th>
                                        <th>Unit Price</th>
                                        <th>Total</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                    `;
                    
                    order.order_items.forEach(item => {
                        html += `
                            <tr>
                                <td>${item.item.item_code} - ${item.item.item_name}</td>
                                <td>${item.requested_quantity}</td>
                                <td>${item.fulfilled_quantity}</td>
                                <td>${item.returnable_quantity}</td>
                                <td>${item.unit_price}</td>
                                <td>${item.total_price}</td>
                                <td><span class="status-${item.status.toLowerCase()}">${item.status}</span></td>
                            </tr>
                        `;
                    });
                    
                    html += `
                                </tbody>
                            </table>
                            <div style="text-align: center; margin-top: 20px;">
                                <button class="btn" onclick="this.closest('.modal').remove()">Close</button>
                            </div>
                        </div>
                    `;
                    
                    const modal = document.createElement('div');
                    modal.className = 'modal';
                    modal.innerHTML = `<div class="modal-content">${html}</div>`;
                    document.body.appendChild(modal);
                    
                } catch (error) {
                    showAlert('Error loading order details: ' + error.message, 'error');
                }
            }

            // ============================
            // CATEGORY MANAGEMENT FUNCTIONS
            // ============================

            async function loadCategories() {
                try {
                    allCategories = await apiCall('/categories');
                    displayCategories();
                } catch (error) {
                    console.error('Error loading categories:', error);
                    showAlert('Error loading categories', 'error');
                }
            }

            function displayCategories() {
                const container = document.getElementById('categories-list');
                
                function renderCategoryTree(categories, level = 0) {
                    return categories.map(category => `
                        <div style="margin-left: ${level * 20}px; border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 10px; background: white;">
                            <h4>${'📁 '.repeat(level + 1)} ${category.name}</h4>
                            <p>${category.description || 'No description'}</p>
                            <p><strong>Created:</strong> ${new Date(category.created_at).toLocaleDateString()}</p>
                            <div style="margin-top: 10px;">
                                ${currentUser.is_admin ? `
                                    <button class="btn btn-danger" onclick="deleteCategory(${category.id})">🗑️ Delete</button>
                                ` : ''}
                            </div>
                            ${category.children && category.children.length > 0 ? renderCategoryTree(category.children, level + 1) : ''}
                        </div>
                    `).join('');
                }
                
                container.innerHTML = renderCategoryTree(allCategories);
            }

            function showAddCategoryModal() {
                loadCategoriesForParentDropdown();
                document.getElementById('add-category-modal').classList.remove('hidden');
            }

            function closeAddCategoryModal() {
                document.getElementById('add-category-modal').classList.add('hidden');
                document.getElementById('add-category-form').reset();
            }

            async function loadCategoriesForParentDropdown() {
                try {
                    const categories = await apiCall('/categories');
                    const select = document.getElementById('parent-category');
                    select.innerHTML = '<option value="">None (Root Category)</option>';
                    
                    function addCategoryOptions(cats, prefix = '') {
                        cats.forEach(cat => {
                            const option = document.createElement('option');
                            option.value = cat.id;
                            option.textContent = prefix + cat.name;
                            select.appendChild(option);
                            
                            if (cat.children && cat.children.length > 0) {
                                addCategoryOptions(cat.children, prefix + '  ');
                            }
                        });
                    }
                    
                    addCategoryOptions(categories);
                } catch (error) {
                    console.error('Error loading categories for dropdown:', error);
                }
            }

            document.getElementById('add-category-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData();
                formData.append('name', document.getElementById('category-name').value);
                formData.append('description', document.getElementById('category-description').value);
                formData.append('parent_id', document.getElementById('parent-category').value);

                try {
                    await fetch('/categories', {
                        method: 'POST',
                        credentials: 'include',
                        body: formData
                    });
                    
                    showAlert('Category created successfully!', 'success');
                    closeAddCategoryModal();
                    loadCategories();
                } catch (error) {
                    showAlert('Error creating category: ' + error.message, 'error');
                }
            });

            async function deleteCategory(categoryId) {
                if (confirm('Are you sure you want to delete this category?')) {
                    try {
                        await fetch(`/categories/${categoryId}`, {
                            method: 'DELETE',
                            credentials: 'include'
                        });
                        
                        showAlert('Category deleted successfully!', 'success');
                        loadCategories();
                    } catch (error) {
                        showAlert('Error deleting category: ' + error.message, 'error');
                    }
                }
            }

            // ============================
            // ITEM MANAGEMENT FUNCTIONS
            // ============================

            async function loadItems() {
                try {
                    allItems = await apiCall('/items');
                    displayItems();
                } catch (error) {
                    console.error('Error loading items:', error);
                    showAlert('Error loading items', 'error');
                }
            }

            function displayItems() {
                const container = document.getElementById('items-list');
                
                container.innerHTML = allItems.map(item => {
                    let cardClass = 'item-card';
                    if (item.current_stock <= item.min_stock_level && item.min_stock_level > 0) {
                        cardClass += ' low-stock';
                    } else if (item.returnable_stock > 0) {
                        cardClass += ' has-returnable';
                    } else {
                        cardClass += ' in-stock';
                    }
                    
                    return `
                        <div class="${cardClass}">
                            <h4>📦 ${item.item_code} - ${item.item_name}</h4>
                            <p><strong>Category:</strong> ${item.category?.name || 'N/A'}</p>
                            <p><strong>Description:</strong> ${item.description || 'No description'}</p>
                            <p><strong>UOM:</strong> ${item.unit_of_measure}</p>
                            <p><strong>Current Stock:</strong> ${item.current_stock} ${item.unit_of_measure}</p>
                            ${item.returnable_stock > 0 ? `<p><strong>Returnable Stock:</strong> ${item.returnable_stock} ${item.unit_of_measure}</p>` : ''}
                            <p><strong>Min/Max Level:</strong> ${item.min_stock_level} / ${item.max_stock_level}</p>
                            <p><strong>Standard Cost:</strong> ${item.standard_cost}</p>
                            <p><strong>Location:</strong> ${item.location || 'Not specified'}</p>
                            <p><strong>Manufacturer:</strong> ${item.manufacturer || 'Not specified'}</p>
                            <p><strong>Returnable:</strong> ${item.is_returnable ? 'Yes' : 'No'}</p>
                            <div style="margin-top: 10px;">
                                <button class="btn btn-success" onclick="stockInItem(${item.id})">📈 Stock In</button>
                                <button class="btn btn-warning" onclick="stockOutItem(${item.id})">📉 Stock Out</button>
                                <button class="btn btn-info" onclick="viewItemHistory(${item.id})">📜 History</button>
                            </div>
                        </div>
                    `;
                }).join('');
            }

            async function loadCategoriesForDropdown() {
                try {
                    const categories = await apiCall('/categories');
                    const selects = [
                        document.getElementById('item-category'),
                        document.getElementById('category-filter')
                    ];
                    
                    function addCategoryOptions(cats, prefix = '') {
                        cats.forEach(cat => {
                            selects.forEach(select => {
                                if (select) {
                                    const option = document.createElement('option');
                                    option.value = cat.id;
                                    option.textContent = prefix + cat.name;
                                    select.appendChild(option);
                                }
                            });
                            
                            if (cat.children && cat.children.length > 0) {
                                addCategoryOptions(cat.children, prefix + '  ');
                            }
                        });
                    }
                    
                    selects.forEach(select => {
                        if (select) {
                            select.innerHTML = select.id === 'category-filter' ? 
                                '<option value="">All Categories</option>' : 
                                '<option value="">Select Category</option>';
                        }
                    });
                    
                    addCategoryOptions(categories);
                } catch (error) {
                    console.error('Error loading categories for dropdown:', error);
                }
            }

            function filterItems() {
                const categoryFilter = document.getElementById('category-filter').value;
                
                if (!categoryFilter) {
                    displayItems();
                    return;
                }
                
                const filteredItems = allItems.filter(item => 
                    item.category && item.category.id == categoryFilter
                );
                
                const container = document.getElementById('items-list');
                container.innerHTML = filteredItems.map(item => {
                    let cardClass = 'item-card';
                    if (item.current_stock <= item.min_stock_level && item.min_stock_level > 0) {
                        cardClass += ' low-stock';
                    } else if (item.returnable_stock > 0) {
                        cardClass += ' has-returnable';
                    } else {
                        cardClass += ' in-stock';
                    }
                    
                    return `
                        <div class="${cardClass}">
                            <h4>📦 ${item.item_code} - ${item.item_name}</h4>
                            <p><strong>Category:</strong> ${item.category?.name || 'N/A'}</p>
                            <p><strong>Description:</strong> ${item.description || 'No description'}</p>
                            <p><strong>UOM:</strong> ${item.unit_of_measure}</p>
                            <p><strong>Current Stock:</strong> ${item.current_stock} ${item.unit_of_measure}</p>
                            ${item.returnable_stock > 0 ? `<p><strong>Returnable Stock:</strong> ${item.returnable_stock} ${item.unit_of_measure}</p>` : ''}
                            <p><strong>Min/Max Level:</strong> ${item.min_stock_level} / ${item.max_stock_level}</p>
                            <p><strong>Standard Cost:</strong> ${item.standard_cost}</p>
                            <p><strong>Location:</strong> ${item.location || 'Not specified'}</p>
                            <p><strong>Returnable:</strong> ${item.is_returnable ? 'Yes' : 'No'}</p>
                            <div style="margin-top: 10px;">
                                <button class="btn btn-success" onclick="stockInItem(${item.id})">📈 Stock In</button>
                                <button class="btn btn-warning" onclick="stockOutItem(${item.id})">📉 Stock Out</button>
                                <button class="btn btn-info" onclick="viewItemHistory(${item.id})">📜 History</button>
                            </div>
                        </div>
                    `;
                }).join('');
            }

            function showAddItemModal() {
                loadCategoriesForDropdown();
                document.getElementById('add-item-modal').classList.remove('hidden');
            }

            function closeAddItemModal() {
                document.getElementById('add-item-modal').classList.add('hidden');
                document.getElementById('add-item-form').reset();
            }

            document.getElementById('add-item-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData();
                formData.append('item_code', document.getElementById('item-code').value);
                formData.append('item_name', document.getElementById('item-name').value);
                formData.append('description', document.getElementById('item-description').value);
                formData.append('category_id', document.getElementById('item-category').value);
                formData.append('unit_of_measure', document.getElementById('item-uom').value);
                formData.append('min_stock_level', document.getElementById('item-min-stock').value);
                formData.append('max_stock_level', document.getElementById('item-max-stock').value);
                formData.append('standard_cost', document.getElementById('item-cost').value);
                formData.append('location', document.getElementById('item-location').value);
                formData.append('manufacturer', document.getElementById('item-manufacturer').value);
                formData.append('model_number', document.getElementById('item-model').value);
                formData.append('specifications', document.getElementById('item-specifications').value);
                formData.append('warranty_months', document.getElementById('item-warranty').value);
                formData.append('is_returnable', document.getElementById('item-is-returnable').checked);

                try {
                    await fetch('/items', {
                        method: 'POST',
                        credentials: 'include',
                        body: formData
                    });
                    
                    showAlert('Item created successfully!', 'success');
                    closeAddItemModal();
                    loadItems();
                } catch (error) {
                    showAlert('Error creating item: ' + error.message, 'error');
                }
            });

            // ============================
            // INVENTORY MANAGEMENT FUNCTIONS
            // ============================

            async function loadInventory() {
                try {
                    allItems = await apiCall('/items');
                    displayInventory();
                } catch (error) {
                    console.error('Error loading inventory:', error);
                    showAlert('Error loading inventory', 'error');
                }
            }

            function displayInventory() {
                const container = document.getElementById('inventory-list');
                
                container.innerHTML = allItems.map(item => {
                    let cardClass = 'item-card';
                    if (item.current_stock <= item.min_stock_level && item.min_stock_level > 0) {
                        cardClass += ' low-stock';
                    } else if (item.returnable_stock > 0) {
                        cardClass += ' has-returnable';
                    } else {
                        cardClass += ' in-stock';
                    }
                    
                    return `
                        <div class="${cardClass}">
                            <h4>📦 ${item.item_code} - ${item.item_name}</h4>
                            <p><strong>Category:</strong> ${item.category?.name || 'N/A'}</p>
                            <p><strong>Current Stock:</strong> ${item.current_stock} ${item.unit_of_measure}</p>
                            ${item.returnable_stock > 0 ? `<p><strong>Returnable Stock:</strong> ${item.returnable_stock} ${item.unit_of_measure}</p>` : ''}
                            <p><strong>Min/Max Level:</strong> ${item.min_stock_level} / ${item.max_stock_level}</p>
                            <p><strong>Location:</strong> ${item.location || 'Not specified'}</p>
                            <p><strong>Returnable:</strong> ${item.is_returnable ? 'Yes' : 'No'}</p>
                            <div style="margin-top: 10px;">
                                <button class="btn btn-success" onclick="stockInItem(${item.id})">📈 Stock In</button>
                                <button class="btn btn-warning" onclick="stockOutItem(${item.id})">📉 Stock Out</button>
                                <button class="btn btn-info" onclick="stockAdjustItem(${item.id})">⚖️ Adjust</button>
                                <button class="btn" onclick="viewItemHistory(${item.id})">📜 History</button>
                            </div>
                        </div>
                    `;
                }).join('');
            }

            function stockInItem(itemId) {
                showStockTransactionModal('IN', itemId);
            }

            function stockOutItem(itemId) {
                showStockTransactionModal('OUT', itemId);
            }

            function stockAdjustItem(itemId) {
                showStockTransactionModal('ADJUST', itemId);
            }

            function showStockInModal() {
                showStockTransactionModal('IN');
            }

            function showStockOutModal() {
                showStockTransactionModal('OUT');
            }

            function showStockAdjustModal() {
                showStockTransactionModal('ADJUST');
            }

            async function showStockTransactionModal(type, itemId = null) {
                const modal = document.getElementById('stock-transaction-modal');
                const title = document.getElementById('transaction-modal-title');
                const typeInput = document.getElementById('transaction-type');
                const subtypeSelect = document.getElementById('transaction-subtype');
                const returnableGroup = document.getElementById('returnable-quantity-group');
                const returnDateGroup = document.getElementById('expected-return-date-group');
                
                typeInput.value = type;
                
                // Set modal title and subtype options
                const subtypes = {
                    'IN': {
                        title: '📈 Stock In Transaction',
                        options: ['PURCHASE', 'RETURN', 'TRANSFER_IN', 'FOUND', 'CUSTOMER_RETURN', 'OTHER']
                    },
                    'OUT': {
                        title: '📉 Stock Out Transaction', 
                        options: ['SALE', 'CONSUMPTION', 'TRANSFER_OUT', 'DAMAGE', 'LOSS', 'ORDER_SHIPMENT', 'CORRECTED','OTHER']
                    },
                    'ADJUST': {
                        title: '⚖️ Stock Adjustment',
                        options: ['STOCK_TAKE', 'CORRECTION', 'RECOUNT', 'OTHER']
                    }
                };
                
                title.textContent = subtypes[type].title;
                subtypeSelect.innerHTML = '<option value="">Select Sub Type</option>';
                subtypes[type].options.forEach(subtype => {
                    subtypeSelect.innerHTML += `<option value="${subtype}">${subtype.replace('_', ' ')}</option>`;
                });
                
                // Show/hide returnable fields based on transaction type
                if (type === 'OUT') {
                    returnableGroup.style.display = 'block';
                    returnDateGroup.style.display = 'block';
                } else {
                    returnableGroup.style.display = 'none';
                    returnDateGroup.style.display = 'none';
                }
                
                // Load items for dropdown
                try {
                    const items = await apiCall('/items');
                    const itemSelect = document.getElementById('transaction-item');
                    itemSelect.innerHTML = '<option value="">Select Item</option>';
                    items.forEach(item => {
                        const option = document.createElement('option');
                        option.value = item.id;
                        option.textContent = `${item.item_code} - ${item.item_name}`;
                        option.dataset.isReturnable = item.is_returnable;
                        if (itemId && item.id === itemId) {
                            option.selected = true;
                        }
                        itemSelect.appendChild(option);
                    });
                } catch (error) {
                    console.error('Error loading items:', error);
                }
                
                modal.classList.remove('hidden');
            }

            function closeStockTransactionModal() {
                document.getElementById('stock-transaction-modal').classList.add('hidden');
                document.getElementById('stock-transaction-form').reset();
            }

            // Update the item selection to show/hide returnable fields
            document.getElementById('transaction-item').addEventListener('change', function() {
                const selectedOption = this.options[this.selectedIndex];
                const returnableGroup = document.getElementById('returnable-quantity-group');
                const returnDateGroup = document.getElementById('expected-return-date-group');
                const transactionType = document.getElementById('transaction-type').value;
                
                if (transactionType === 'OUT' && selectedOption.dataset.isReturnable === 'true') {
                    returnableGroup.style.display = 'block';
                    returnDateGroup.style.display = 'block';
                } else if (transactionType === 'OUT') {
                    returnableGroup.style.display = 'none';
                    returnDateGroup.style.display = 'none';
                }
            });

            document.getElementById('stock-transaction-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData();
                formData.append('item_master_id', document.getElementById('transaction-item').value);
                formData.append('transaction_type', document.getElementById('transaction-type').value);
                formData.append('transaction_sub_type', document.getElementById('transaction-subtype').value);
                formData.append('quantity', document.getElementById('transaction-quantity').value);
                formData.append('returnable_quantity', document.getElementById('transaction-returnable-quantity').value || '0');
                formData.append('unit_cost', document.getElementById('transaction-cost').value);
                formData.append('reference_number', document.getElementById('transaction-reference').value);
                formData.append('vendor_customer', document.getElementById('transaction-vendor').value);
                formData.append('expected_return_date', document.getElementById('transaction-expected-return').value);
                formData.append('remarks', document.getElementById('transaction-remarks').value);

                try {
                    const result = await fetch('/inventory/transactions', {
                        method: 'POST',
                        credentials: 'include',
                        body: formData
                    });
                    
                    if (result.ok) {
                        const data = await result.json();
                        
                        if (confirm('Transaction created successfully! Do you want to confirm it now?')) {
                            await fetch(`/inventory/transactions/${data.transaction_id}/confirm`, {
                                method: 'POST',
                                credentials: 'include'
                            });
                            showAlert('Transaction confirmed successfully!', 'success');
                        } else {
                            showAlert('Transaction created successfully!', 'success');
                        }
                        
                        closeStockTransactionModal();
                        loadInventory();
                        loadDashboard();
                    }
                } catch (error) {
                    showAlert('Error creating transaction: ' + error.message, 'error');
                }
            });

            // ============================
            // TRANSACTION MANAGEMENT FUNCTIONS
            // ============================

            async function loadTransactions() {
                try {
                    allTransactions = await apiCall('/inventory/transactions');
                    displayTransactions();
                } catch (error) {
                    console.error('Error loading transactions:', error);
                    showAlert('Error loading transactions', 'error');
                }
            }

            function displayTransactions() {
                const container = document.getElementById('transactions-list');
                
                if (allTransactions.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #666; padding: 40px;">No transactions found.</p>';
                    return;
                }
                
                let tableHTML = `
                    <table>
                        <thead>
                            <tr>
                                <th>Transaction #</th>
                                <th>Date</th>
                                <th>Item</th>
                                <th>Order</th>
                                <th>Type</th>
                                <th>Sub Type</th>
                                <th>Quantity</th>
                                <th>Returnable</th>
                                <th>Cost</th>
                                <th>Status</th>
                                <th>User</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                allTransactions.forEach(txn => {
                    const statusColor = txn.status === 'CONFIRMED' ? '#27ae60' : 
                                       txn.status === 'PENDING' ? '#f39c12' : '#e74c3c';
                    
                    tableHTML += `
                        <tr>
                            <td>${txn.transaction_number}</td>
                            <td>${new Date(txn.transaction_date).toLocaleDateString()}</td>
                            <td>${txn.item?.item_code || 'N/A'} - ${txn.item?.item_name || 'N/A'}</td>
                            <td>${txn.order ? `${txn.order.order_number} - ${txn.order.customer_name}` : 'N/A'}</td>
                            <td>${txn.transaction_type}</td>
                            <td>${txn.transaction_sub_type}</td>
                            <td>${txn.quantity}</td>
                            <td>${txn.returnable_quantity || 0}</td>
                            <td>${txn.total_cost}</td>
                            <td><span style="color: ${statusColor}; font-weight: bold;">${txn.status}</span></td>
                            <td>${txn.user?.name || 'N/A'}</td>
                            <td>
                                ${txn.status === 'PENDING' ? `<button class="btn btn-success" onclick="confirmTransaction(${txn.id})">✅ Confirm</button>` : ''}
                                <button class="btn btn-info" onclick="viewTransactionDetails(${txn.id})">👁️ View</button>
                            </td>
                        </tr>
                    `;
                });
                
                tableHTML += '</tbody></table>';
                container.innerHTML = tableHTML;
            }

            function filterTransactions() {
                const typeFilter = document.getElementById('transaction-type-filter').value;
                const statusFilter = document.getElementById('transaction-status-filter').value;
                
                let filteredTransactions = allTransactions;
                
                if (typeFilter) {
                    filteredTransactions = filteredTransactions.filter(txn => txn.transaction_type === typeFilter);
                }
                
                if (statusFilter) {
                    filteredTransactions = filteredTransactions.filter(txn => txn.status === statusFilter);
                }
                
                const container = document.getElementById('transactions-list');
                
                if (filteredTransactions.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #666; padding: 40px;">No transactions found matching the filters.</p>';
                    return;
                }
                
                let tableHTML = `
                    <table>
                        <thead>
                            <tr>
                                <th>Transaction #</th>
                                <th>Date</th>
                                <th>Item</th>
                                <th>Order</th>
                                <th>Type</th>
                                <th>Sub Type</th>
                                <th>Quantity</th>
                                <th>Returnable</th>
                                <th>Cost</th>
                                <th>Status</th>
                                <th>User</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                filteredTransactions.forEach(txn => {
                    const statusColor = txn.status === 'CONFIRMED' ? '#27ae60' : 
                                       txn.status === 'PENDING' ? '#f39c12' : '#e74c3c';
                    
                    tableHTML += `
                        <tr>
                            <td>${txn.transaction_number}</td>
                            <td>${new Date(txn.transaction_date).toLocaleDateString()}</td>
                            <td>${txn.item?.item_code || 'N/A'} - ${txn.item?.item_name || 'N/A'}</td>
                            <td>${txn.order ? `${txn.order.order_number} - ${txn.order.customer_name}` : 'N/A'}</td>
                            <td>${txn.transaction_type}</td>
                            <td>${txn.transaction_sub_type}</td>
                            <td>${txn.quantity}</td>
                            <td>${txn.returnable_quantity || 0}</td>
                            <td>${txn.total_cost}</td>
                            <td><span style="color: ${statusColor}; font-weight: bold;">${txn.status}</span></td>
                            <td>${txn.user?.name || 'N/A'}</td>
                            <td>
                                ${txn.status === 'PENDING' ? `<button class="btn btn-success" onclick="confirmTransaction(${txn.id})">✅ Confirm</button>` : ''}
                                <button class="btn btn-info" onclick="viewTransactionDetails(${txn.id})">👁️ View</button>
                            </td>
                        </tr>
                    `;
                });
                
                tableHTML += '</tbody></table>';
                container.innerHTML = tableHTML;
            }

            async function confirmTransaction(transactionId) {
                if (confirm('Are you sure you want to confirm this transaction? This will update the inventory levels.')) {
                    try {
                        await fetch(`/inventory/transactions/${transactionId}/confirm`, {
                            method: 'POST',
                            credentials: 'include'
                        });
                        
                        showAlert('Transaction confirmed successfully!', 'success');
                        loadTransactions();
                        loadInventory();
                        loadDashboard();
                    } catch (error) {
                        showAlert('Error confirming transaction: ' + error.message, 'error');
                    }
                }
            }

            async function viewItemHistory(itemId) {
                try {
                    const transactions = await apiCall(`/inventory/transactions?item_id=${itemId}`);
                    
                    let html = `
                        <div style="max-width: 900px;">
                            <h3>📜 Item Transaction History</h3>
                            <table style="margin-top: 20px;">
                                <thead>
                                    <tr>
                                        <th>Date</th>
                                        <th>Type</th>
                                        <th>Sub Type</th>
                                        <th>Quantity</th>
                                        <th>Returnable</th>
                                        <th>Cost</th>
                                        <th>Reference</th>
                                        <th>Customer/Vendor</th>
                                        <th>Status</th>
                                        <th>User</th>
                                    </tr>
                                </thead>
                                <tbody>
                    `;
                    
                    transactions.forEach(txn => {
                        const statusColor = txn.status === 'CONFIRMED' ? '#27ae60' : 
                                           txn.status === 'PENDING' ? '#f39c12' : '#e74c3c';
                        
                        html += `
                            <tr>
                                <td>${new Date(txn.transaction_date).toLocaleDateString()}</td>
                                <td>${txn.transaction_type}</td>
                                <td>${txn.transaction_sub_type}</td>
                                <td>${txn.quantity}</td>
                                <td>${txn.returnable_quantity || 0}</td>
                                <td>${txn.total_cost}</td>
                                <td>${txn.reference_number || 'N/A'}</td>
                                <td>${txn.vendor_customer || 'N/A'}</td>
                                <td><span style="color: ${statusColor}; font-weight: bold;">${txn.status}</span></td>
                                <td>${txn.user?.name || 'N/A'}</td>
                            </tr>
                        `;
                    });
                    
                    html += `
                                </tbody>
                            </table>
                            <div style="text-align: center; margin-top: 20px;">
                                <button class="btn" onclick="this.closest('.modal').remove()">Close</button>
                            </div>
                        </div>
                    `;
                    
                    const modal = document.createElement('div');
                    modal.className = 'modal';
                    modal.innerHTML = `<div class="modal-content">${html}</div>`;
                    document.body.appendChild(modal);
                    
                } catch (error) {
                    showAlert('Error loading item history: ' + error.message, 'error');
                }
            }

            // ============================
            // RETURNABLE ITEMS MANAGEMENT
            // ============================

            async function loadReturnableItems() {
                try {
                    allReturnableItems = await apiCall('/inventory/returnable-items');
                    displayReturnableItems();
                } catch (error) {
                    console.error('Error loading returnable items:', error);
                    showAlert('Error loading returnable items', 'error');
                }
            }

            function displayReturnableItems() {
                const container = document.getElementById('returnable-items-list');
                
                if (allReturnableItems.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #666; padding: 40px;">No returnable items found.</p>';
                    return;
                }
                
                container.innerHTML = allReturnableItems.map(item => `
                    <div class="returnable-card ${item.is_overdue ? 'overdue-card' : ''}">
                        <h4>🔄 ${item.item.item_code} - ${item.item.item_name}</h4>
                        <p><strong>Transaction:</strong> ${item.transaction_number}</p>
                        <p><strong>Customer:</strong> ${item.customer_name}</p>
                        <p><strong>Total Returnable:</strong> ${item.total_returnable}</p>
                        <p><strong>Returned:</strong> ${item.returned_quantity}</p>
                        <p><strong>Outstanding:</strong> ${item.outstanding_quantity}</p>
                        <p><strong>Transaction Date:</strong> ${new Date(item.transaction_date).toLocaleDateString()}</p>
                        <p><strong>Expected Return:</strong> ${item.expected_return_date ? new Date(item.expected_return_date).toLocaleDateString() : 'Not specified'}</p>
                        ${item.is_overdue ? '<p style="color: #e74c3c; font-weight: bold;">⚠️ OVERDUE</p>' : ''}
                        <div style="margin-top: 10px;">
                            <button class="btn btn-success" onclick="showProcessReturnModal(${item.transaction_id}, ${item.outstanding_quantity})">✅ Process Return</button>
                        </div>
                    </div>
                `).join('');
            }

            function showProcessReturnModal(transactionId, maxQuantity) {
                const modal = document.createElement('div');
                modal.className = 'modal';
                modal.innerHTML = `
                    <div class="modal-content">
                        <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
                        <h3>🔄 Process Return</h3>
                        <form id="process-return-form">
                            <div class="form-group">
                                <label for="return-quantity">Returned Quantity:</label>
                                <input type="number" id="return-quantity" step="0.001" required max="${maxQuantity}" value="${maxQuantity}">
                            </div>
                            <div class="form-group">
                                <label for="return-condition">Condition:</label>
                                <select id="return-condition" required>
                                    <option value="">Select Condition</option>
                                    <option value="GOOD">Good - Can be restocked</option>
                                    <option value="DAMAGED">Damaged - Needs repair</option>
                                    <option value="UNUSABLE">Unusable - Write off</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="return-remarks">Remarks:</label>
                                <textarea id="return-remarks"></textarea>
                            </div>
                            <button type="submit" class="btn">Process Return</button>
                        </form>
                    </div>
                `;
                document.body.appendChild(modal);

                document.getElementById('process-return-form').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    
                    const formData = new FormData();
                    formData.append('transaction_id', transactionId);
                    formData.append('returned_quantity', document.getElementById('return-quantity').value);
                    formData.append('condition', document.getElementById('return-condition').value);
                    formData.append('remarks', document.getElementById('return-remarks').value);

                    try {
                        await fetch('/inventory/process-return', {
                            method: 'POST',
                            credentials: 'include',
                            body: formData
                        });
                        
                        showAlert('Return processed successfully!', 'success');
                        modal.remove();
                        loadReturnableItems();
                        loadDashboard();
                    } catch (error) {
                        showAlert('Error processing return: ' + error.message, 'error');
                    }
                });
            }

            // ============================
            // ADMIN FUNCTIONS
            // ============================

            async function loadUsers() {
                if (!currentUser?.is_admin) return;
                
                try {
                    const users = await apiCall('/admin/users');
                    const departments = await apiCall('/departments');
                    
                    // Load departments for user form
                    const deptSelect = document.getElementById('user-department');
                    if (deptSelect) {
                        deptSelect.innerHTML = '<option value="">Select Department</option>';
                        departments.forEach(dept => {
                            deptSelect.innerHTML += `<option value="${dept.id}">${dept.name}</option>`;
                        });
                    }
                    
                    displayUsers(users);
                } catch (error) {
                    console.error('Error loading users:', error);
                    showAlert('Error loading users', 'error');
                }
            }

            function displayUsers(users) {
                const container = document.getElementById('users-list');
                
                let html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Employee ID</th>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Department</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                users.forEach(user => {
                    html += `
                        <tr>
                            <td>${user.employee_id}</td>
                            <td>${user.name}</td>
                            <td>${user.email}</td>
                            <td>${user.department?.name || 'N/A'}</td>
                            <td>${user.is_admin ? 'Admin' : 'User'}</td>
                            <td><span style="color: ${user.is_active ? '#27ae60' : '#e74c3c'};">${user.is_active ? 'Active' : 'Inactive'}</span></td>
                            <td>
                                ${user.id !== currentUser.id ? `<button class="btn btn-danger" onclick="deleteUser(${user.id})">🗑️</button>` : ''}
                            </td>
                        </tr>
                    `;
                });
                
                html += '</tbody></table>';
                container.innerHTML = html;
            }

            function showAddUserModal() {
                document.getElementById('add-user-modal').classList.remove('hidden');
            }

            function closeAddUserModal() {
                document.getElementById('add-user-modal').classList.add('hidden');
                document.getElementById('add-user-form').reset();
            }

            document.getElementById('add-user-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData();
                formData.append('employee_id', document.getElementById('user-employee-id').value);
                formData.append('name', document.getElementById('user-name').value);
                formData.append('email', document.getElementById('user-email').value);
                formData.append('password', document.getElementById('user-password').value);
                formData.append('department_id', document.getElementById('user-department').value);
                formData.append('is_admin', document.getElementById('user-is-admin').checked);

                try {
                    await fetch('/admin/users', {
                        method: 'POST',
                        credentials: 'include',
                        body: formData
                    });
                    
                    showAlert('User created successfully!', 'success');
                    closeAddUserModal();
                    loadUsers();
                } catch (error) {
                    showAlert('Error creating user: ' + error.message, 'error');
                }
            });

            async function loadDepartments() {
                if (!currentUser?.is_admin) return;
                
                try {
                    const departments = await apiCall('/admin/departments-with-users');
                    const divisions = await apiCall('/divisions');
                    
                    // Load divisions for department form
                    const divSelect = document.getElementById('dept-division');
                    if (divSelect) {
                        divSelect.innerHTML = '<option value="">Select Division</option>';
                        divisions.forEach(div => {
                            divSelect.innerHTML += `<option value="${div.id}">${div.name}</option>`;
                        });
                    }
                    
                    displayDepartments(departments);
                } catch (error) {
                    console.error('Error loading departments:', error);
                    showAlert('Error loading departments', 'error');
                }
            }

            function displayDepartments(departments) {
                const container = document.getElementById('departments-list');
                
                let html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Description</th>
                                <th>Division</th>
                                <th>Users</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                departments.forEach(dept => {
                    html += `
                        <tr>
                            <td>${dept.name}</td>
                            <td>${dept.description || 'N/A'}</td>
                            <td>${dept.division?.name || 'N/A'}</td>
                            <td>${dept.user_count || 0}</td>
                            <td>
                                <button class="btn btn-danger" onclick="deleteDepartment(${dept.id})">🗑️</button>
                            </td>
                        </tr>
                    `;
                });
                
                html += '</tbody></table>';
                container.innerHTML = html;
            }

            function showAddDepartmentModal() {
                document.getElementById('add-department-modal').classList.remove('hidden');
            }

            function closeAddDepartmentModal() {
                document.getElementById('add-department-modal').classList.add('hidden');
                document.getElementById('add-department-form').reset();
            }

            document.getElementById('add-department-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData();
                formData.append('name', document.getElementById('dept-name').value);
                formData.append('description', document.getElementById('dept-description').value);
                formData.append('division_id', document.getElementById('dept-division').value);

                try {
                    await fetch('/admin/departments', {
                        method: 'POST',
                        credentials: 'include',
                        body: formData
                    });
                    
                    showAlert('Department created successfully!', 'success');
                    closeAddDepartmentModal();
                    loadDepartments();
                } catch (error) {
                    showAlert('Error creating department: ' + error.message, 'error');
                }
            });

            async function loadDivisions() {
                if (!currentUser?.is_admin) return;
                
                try {
                    const divisions = await apiCall('/admin/divisions-with-departments');
                    displayDivisions(divisions);
                } catch (error) {
                    console.error('Error loading divisions:', error);
                    showAlert('Error loading divisions', 'error');
                }
            }

            function displayDivisions(divisions) {
                const container = document.getElementById('divisions-list');
                
                let html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Description</th>
                                <th>Type</th>
                                <th>Departments</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                divisions.forEach(div => {
                    html += `
                        <tr>
                            <td>${div.name}</td>
                            <td>${div.description || 'N/A'}</td>
                            <td>${div.is_default ? 'Default' : 'Custom'}</td>
                            <td>${div.department_count || 0}</td>
                            <td>
                                ${!div.is_default ? `<button class="btn btn-danger" onclick="deleteDivision(${div.id})">🗑️</button>` : '<span style="color: #666;">Protected</span>'}
                            </td>
                        </tr>
                    `;
                });
                
                html += '</tbody></table>';
                container.innerHTML = html;
            }

            function showAddDivisionModal() {
                document.getElementById('add-division-modal').classList.remove('hidden');
            }

            function closeAddDivisionModal() {
                document.getElementById('add-division-modal').classList.add('hidden');
                document.getElementById('add-division-form').reset();
            }

            document.getElementById('add-division-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData();
                formData.append('name', document.getElementById('div-name').value);
                formData.append('description', document.getElementById('div-description').value);

                try {
                    await fetch('/admin/divisions', {
                        method: 'POST',
                        credentials: 'include',
                        body: formData
                    });
                    
                    showAlert('Division created successfully!', 'success');
                    closeAddDivisionModal();
                    loadDivisions();
                } catch (error) {
                    showAlert('Error creating division: ' + error.message, 'error');
                }
            });


            // ============================
            // ORDER FULFILLMENT FUNCTIONS
            // ============================

            async function showOrderFulfillmentModal() {
                try {
                    const orders = await apiCall('/orders/pending-fulfillment');
                    
                    if (orders.length === 0) {
                        showAlert('No pending orders found for fulfillment', 'info');
                        return;
                    }
                    
                    const modal = document.createElement('div');
                    modal.className = 'modal';
                    modal.innerHTML = `
                        <div class="modal-content" style="max-width: 1000px;">
                            <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
                            <h3>📋 Order Fulfillment</h3>
                            <div style="margin: 20px 0;">
                                <label for="fulfillment-order-select">Select Order:</label>
                                <select id="fulfillment-order-select" style="width: 100%; padding: 10px; margin-top: 5px;" onchange="loadOrderForFulfillment(this.value)">
                                    <option value="">Select an order...</option>
                                    ${orders.map(order => `
                                        <option value="${order.id}">${order.order_number} - ${order.customer_name} ($${order.total_amount})</option>
                                    `).join('')}
                                </select>
                            </div>
                            <div id="order-fulfillment-details" style="display: none;">
                                <div id="order-info"></div>
                                <div id="fulfillment-items"></div>
                                <div style="margin-top: 20px; text-align: center;">
                                    <button class="btn btn-success" onclick="bulkFulfillOrder()">✅ Fulfill Entire Order</button>
                                    <button class="btn" onclick="this.closest('.modal').remove()">Cancel</button>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    document.body.appendChild(modal);
                    
                    // Store orders data for later use
                    window.fulfillmentOrders = orders;
                    
                } catch (error) {
                    showAlert('Error loading orders for fulfillment: ' + error.message, 'error');
                }
            }

            function loadOrderForFulfillment(orderId) {
                if (!orderId) {
                    document.getElementById('order-fulfillment-details').style.display = 'none';
                    return;
                }
                
                const order = window.fulfillmentOrders.find(o => o.id == orderId);
                if (!order) return;
                
                // Display order information
                document.getElementById('order-info').innerHTML = `
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                        <h4>Order Details</h4>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                            <div>
                                <p><strong>Order Number:</strong> ${order.order_number}</p>
                                <p><strong>Customer:</strong> ${order.customer_name}</p>
                                <p><strong>Contact:</strong> ${order.customer_contact}</p>
                            </div>
                            <div>
                                <p><strong>Order Date:</strong> ${new Date(order.order_date).toLocaleDateString()}</p>
                                <p><strong>Expected Delivery:</strong> ${order.expected_delivery_date ? new Date(order.expected_delivery_date).toLocaleDateString() : 'Not specified'}</p>
                                <p><strong>Total Amount:</strong> $${order.total_amount}</p>
                            </div>
                        </div>
                        <p><strong>Notes:</strong> ${order.notes || 'None'}</p>
                    </div>
                `;
                
                // Display order items
                let itemsHTML = `
                    <h4>Order Items</h4>
                    <div style="overflow-x: auto;">
                        <table style="width: 100%; margin-top: 10px;">
                            <thead>
                                <tr>
                                    <th style="text-align: left;">Item</th>
                                    <th>Requested</th>
                                    <th>Fulfilled</th>
                                    <th>Remaining</th>
                                    <th>Available Stock</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                `;
                
                order.order_items.forEach(item => {
                    const remainingQty = item.requested_quantity - item.fulfilled_quantity;
                    const canFulfill = remainingQty > 0 && item.available_stock >= remainingQty;
                    
                    itemsHTML += `
                        <tr>
                            <td>
                                <strong>${item.item_code}</strong><br>
                                ${item.item_name}
                                ${item.is_returnable ? '<br><small style="color: #f39c12;">📦 Returnable</small>' : ''}
                            </td>
                            <td>${item.requested_quantity} ${item.unit_of_measure}</td>
                            <td>${item.fulfilled_quantity} ${item.unit_of_measure}</td>
                            <td style="font-weight: bold; color: ${remainingQty > 0 ? '#e74c3c' : '#27ae60'};">${remainingQty} ${item.unit_of_measure}</td>
                            <td style="color: ${item.available_stock >= remainingQty ? '#27ae60' : '#e74c3c'}; font-weight: bold;">
                                ${item.available_stock} ${item.unit_of_measure}
                            </td>
                            <td><span class="status-${item.status.toLowerCase()}">${item.status}</span></td>
                            <td>
                                ${remainingQty > 0 ? `
                                    <button class="btn ${canFulfill ? 'btn-success' : 'btn-danger'}" ${canFulfill ? '' : 'disabled'} 
                                            onclick="showItemFulfillmentModal(${order.id}, ${item.id}, ${remainingQty}, '${item.item_code}', '${item.item_name}', ${item.is_returnable}, '${item.unit_of_measure}', ${item.available_stock})">
                                        ${canFulfill ? '✅ Fulfill' : '⚠️ No Stock'}
                                    </button>
                                ` : '<span style="color: #27ae60; font-weight: bold;">✅ Complete</span>'}
                            </td>
                        </tr>
                    `;
                });
                
                itemsHTML += '</tbody></table></div>';
                
                document.getElementById('fulfillment-items').innerHTML = itemsHTML;
                document.getElementById('order-fulfillment-details').style.display = 'block';
                
                // Store current order for bulk fulfillment
                window.currentFulfillmentOrder = order;
            }

            function showItemFulfillmentModal(orderId, orderItemId, maxQuantity, itemCode, itemName, isReturnable, unitOfMeasure, availableStock) {
                const modal = document.createElement('div');
                modal.className = 'modal';
                modal.innerHTML = `
                    <div class="modal-content">
                        <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
                        <h3>📦 Fulfill Item: ${itemCode}</h3>
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
                            <p><strong>Item:</strong> ${itemName}</p>
                            <p><strong>Remaining to Fulfill:</strong> ${maxQuantity} ${unitOfMeasure}</p>
                            <p><strong>Available Stock:</strong> ${availableStock} ${unitOfMeasure}</p>
                            ${isReturnable ? '<p><strong>Type:</strong> <span style="color: #f39c12;">📦 Returnable Item</span></p>' : ''}
                        </div>
                        
                        <form id="item-fulfillment-form">
                            <div class="form-group">
                                <label for="fulfill-quantity">Fulfill Quantity (${unitOfMeasure}):</label>
                                <input type="number" id="fulfill-quantity" step="0.001" 
                                       min="0.001" max="${maxQuantity}" value="${maxQuantity}" required>
                                <small>Maximum: ${maxQuantity} ${unitOfMeasure}</small>
                            </div>
                            
                            ${isReturnable ? `
                                <div class="form-group">
                                    <label for="extra-quantity">Extra Quantity - Returnable (${unitOfMeasure}):</label>
                                    <input type="number" id="extra-quantity" step="0.001" 
                                           min="0" max="${availableStock - maxQuantity}" value="0">
                                    <small>Additional quantity that customer can return later (Max: ${availableStock - maxQuantity})</small>
                                </div>
                                
                                <div class="form-group">
                                    <label for="expected-return-date">Expected Return Date:</label>
                                    <input type="date" id="expected-return-date" min="${new Date().toISOString().split('T')[0]}">
                                </div>
                            ` : ''}
                            
                            <div class="form-group">
                                <label for="fulfillment-remarks">Remarks:</label>
                                <textarea id="fulfillment-remarks" placeholder="Optional remarks for this fulfillment"></textarea>
                            </div>
                            
                            <div style="text-align: center;">
                                <button type="submit" class="btn btn-success">✅ Fulfill Item</button>
                                <button type="button" class="btn" onclick="this.closest('.modal').remove()">Cancel</button>
                            </div>
                        </form>
                    </div>
                `;
                
                document.body.appendChild(modal);
                
                // Add real-time calculation
                const fulfillQty = document.getElementById('fulfill-quantity');
                const extraQty = document.getElementById('extra-quantity');
                
                function updateTotalQty() {
                    const fulfill = parseFloat(fulfillQty.value) || 0;
                    const extra = parseFloat(extraQty?.value) || 0;
                    const total = fulfill + extra;
                    
                    if (total > availableStock) {
                        if (extraQty) {
                            extraQty.value = Math.max(0, availableStock - fulfill);
                        }
                    }
                }
                
                fulfillQty.addEventListener('input', updateTotalQty);
                if (extraQty) {
                    extraQty.addEventListener('input', updateTotalQty);
                }
                
                document.getElementById('item-fulfillment-form').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    
                    const formData = new FormData();
                    formData.append('order_item_id', orderItemId);
                    formData.append('fulfill_quantity', document.getElementById('fulfill-quantity').value);
                    formData.append('extra_quantity', document.getElementById('extra-quantity')?.value || '0');
                    formData.append('expected_return_date', document.getElementById('expected-return-date')?.value || '');
                    formData.append('remarks', document.getElementById('fulfillment-remarks').value);
                    
                    try {
                        const response = await fetch(`/orders/${orderId}/fulfill-item`, {
                            method: 'POST',
                            credentials: 'include',
                            body: formData
                        });
                        
                        if (response.ok) {
                            const result = await response.json();
                            showAlert(result.message, 'success');
                            modal.remove();
                            
                            // Refresh the fulfillment modal
                            const orderSelect = document.getElementById('fulfillment-order-select');
                            if (orderSelect) {
                                // Reload orders data
                                const orders = await apiCall('/orders/pending-fulfillment');
                                window.fulfillmentOrders = orders;
                                loadOrderForFulfillment(orderSelect.value);
                            }
                            
                            // Refresh inventory and dashboard
                            loadInventory();
                            loadDashboard();
                        } else {
                            const errorText = await response.text();
                            throw new Error(errorText);
                        }
                    } catch (error) {
                        showAlert('Error fulfilling item: ' + error.message, 'error');
                    }
                });
            }

            async function bulkFulfillOrder() {
                if (!window.currentFulfillmentOrder) return;
                
                const order = window.currentFulfillmentOrder;
                const remainingItems = order.order_items.filter(item => 
                    item.requested_quantity > item.fulfilled_quantity
                );
                
                if (remainingItems.length === 0) {
                    showAlert('All items in this order are already fulfilled!', 'info');
                    return;
                }
                
                let confirmMessage = `Are you sure you want to fulfill the entire order ${order.order_number}?\\n\\n`;
                confirmMessage += `This will fulfill the following items:\\n`;
                
                remainingItems.forEach(item => {
                    const remainingQty = item.requested_quantity - item.fulfilled_quantity;
                    confirmMessage += `- ${item.item_code}: ${remainingQty} ${item.unit_of_measure}\\n`;
                });
                
                const confirmed = confirm(confirmMessage);
                if (!confirmed) return;
                
                try {
                    const response = await fetch(`/orders/${order.id}/bulk-fulfill`, {
                        method: 'POST',
                        credentials: 'include'
                    });
                    
                    if (response.ok) {
                        const result = await response.json();
                        showAlert(result.message, 'success');
                        
                        // Close the fulfillment modal
                        const modal = document.querySelector('.modal');
                        if (modal) modal.remove();
                        
                        // Refresh data
                        loadOrders();
                        loadInventory();
                        loadDashboard();
                    } else {
                        const errorText = await response.text();
                        throw new Error(errorText);
                    }
                } catch (error) {
                    showAlert('Error fulfilling order: ' + error.message, 'error');
                }
            }


            // ============================
            // INITIALIZE APPLICATION
            // ============================

            document.addEventListener('DOMContentLoaded', function() {
                console.log('🚀 DigiAssets Complete Inventory Management System loaded');
                console.log('📊 Database validation enabled');
                console.log('🔍 Real-time monitoring active');
                console.log('🎯 All functionalities implemented');
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)