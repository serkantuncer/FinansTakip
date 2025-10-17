-- Migration to add user support to existing database
-- This will be handled by the Flask app automatically

-- Add user_id column to yatirim table if it doesn't exist
ALTER TABLE yatirim ADD COLUMN user_id INTEGER;

-- Add user_id column to fiyat_gecmisi table if it doesn't exist  
ALTER TABLE fiyat_gecmisi ADD COLUMN user_id INTEGER;

-- Note: Foreign key constraints will be handled by SQLAlchemy
-- The Flask app will create the User table automatically
