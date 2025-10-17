# Financial Portfolio Tracking System

## Overview

This is a Flask-based financial portfolio tracking application that allows users to monitor their investments across multiple asset types including stocks, funds, gold, and foreign currencies. The system provides real-time price updates, portfolio analytics with interactive visualizations, and multi-user support with authentication. Users can track their investments, view historical performance, and export portfolio reports.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Technology Stack:**
- Bootstrap 5.3 with dark theme for responsive UI
- Plotly.js for interactive charts and data visualization
- Font Awesome for icons
- Vanilla JavaScript for client-side interactions (search, filters, tooltips)

**Key Design Patterns:**
- Template inheritance using Jinja2 base templates (`base.html`)
- Real-time search and filtering without page reloads
- Modal-based forms for adding/editing investments
- Responsive card-based dashboard layout

**Rationale:** Bootstrap provides quick responsive layouts while Plotly enables rich financial visualizations. The template-based approach minimizes code duplication across pages.

### Backend Architecture

**Technology Stack:**
- Flask 3.1.1 as the web framework
- SQLAlchemy 2.0 as the ORM
- Flask-Login for user session management
- Flask-Migrate for database migrations
- BeautifulSoup4 for web scraping price data

**Application Structure:**
- `app.py`: Main Flask application with route handlers and business logic
- `auth.py`: Authentication blueprint for login/register/logout
- `models.py`: SQLAlchemy models (User, Yatirim, FiyatGecmisi)
- `main.py`: Desktop application wrapper using Tkinter (optional GUI launcher)

**Key Design Decisions:**

1. **Blueprint-based routing:** Authentication is separated into its own blueprint for modularity
2. **User-scoped data:** All investments are linked to users via foreign keys, enabling multi-tenant functionality
3. **Price tracking:** Separate `FiyatGecmisi` model stores historical prices for trend analysis
4. **Decimal precision:** Uses `Decimal` type with high precision (20,6) for financial calculations to avoid floating-point errors

**Alternatives Considered:**
- Single-file application: Rejected in favor of modular blueprint approach for better organization
- NoSQL database: Rejected because relational structure better suits investment tracking with foreign keys

### Data Storage

**Database:** SQLite (development/standalone), with potential for PostgreSQL in production

**Schema Design:**

1. **User Table:**
   - Standard authentication fields (username, email, password_hash)
   - One-to-many relationship with investments and price history

2. **Yatirim (Investment) Table:**
   - Supports multiple asset types (fon, hisse, altin, doviz)
   - Stores both purchase price and current price
   - Includes separate buy/sell prices for gold and currency
   - Flexible decimal fields for quantity and prices
   - Optional notes and category fields

3. **FiyatGecmisi (Price History) Table:**
   - Tracks historical price data for trend analysis
   - User-scoped for privacy

**Migration Strategy:**
- Flask-Migrate (Alembic) handles schema changes
- `user_id` foreign key added with nullable=True for backward compatibility

**Rationale:** SQLite provides zero-configuration setup for standalone use, while the schema design supports multiple asset types in a single table using a discriminator column (`tip`). This avoids table proliferation while maintaining flexibility.

### Authentication & Authorization

**Mechanism:** Flask-Login with Werkzeug password hashing

**Features:**
- Session-based authentication with "remember me" functionality
- Password hashing using `generate_password_hash`/`check_password_hash`
- Protected routes using `@login_required` decorator
- User context available via `current_user` proxy

**Security Measures:**
- Passwords stored as hashed values only
- CSRF protection through Flask forms
- Next-page redirect validation to prevent open redirects

### External Dependencies

**Price Data Sources:**
- Web scraping using BeautifulSoup4 and requests
- Scrapes financial websites for real-time price updates
- Data sources vary by asset type (stocks, currencies, commodities)

**Third-party Libraries:**
- **Plotly:** Interactive financial charts (line charts, pie charts for portfolio distribution)
- **Pandas:** Data manipulation for aggregations and exports
- **PyInstaller:** Bundles application as standalone executable (via `YatirimTakip.spec`)
- **Tkinter/ttkbootstrap:** Optional desktop GUI wrapper for the web application

**Platform Considerations:**
- Cross-platform support (Windows, macOS, Linux)
- Special handling for PyInstaller frozen applications (resource paths, writable database location)
- macOS-specific post-build scripts for `.dylib` path fixes

**Deployment Options:**
1. **Standalone Desktop App:** PyInstaller bundles Flask app with embedded browser interface
2. **Web Server:** Traditional Flask deployment with WSGI server
3. **Development:** Flask development server with auto-reload

**Rationale:** Web scraping provides free real-time data without API dependencies or costs. PyInstaller packaging makes distribution simple for non-technical users. The dual deployment model (web + desktop) maximizes accessibility.