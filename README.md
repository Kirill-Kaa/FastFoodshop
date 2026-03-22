# Food Store Website

A simple food delivery website built with Flask and Bootstrap.

## Features

- Product catalog with category filtering
- SQLite database with sample products
- Responsive Bootstrap design
- Product detail pages
- Clean and modern UI

## Setup Instructions

1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

2. **Run the Application**
```bash
python app.py
```

3. **Access the Website**
Open your browser and go to: `http://localhost:5000`

## Project Structure

```
├── app.py                 # Main Flask application
├── food_store.db          # SQLite database (auto-created)
├── requirements.txt       # Python dependencies
├── templates/
│   ├── base.html         # Base template
│   ├── index.html        # Home page
│   ├── catalog.html      # Product catalog
│   └── product.html      # Product detail page
└── static/
    └── css/              # Additional CSS (if needed)
```

## Database Schema

**products** table:
- id (INTEGER PRIMARY KEY)
- name (TEXT)
- description (TEXT)
- price (REAL)
- category (TEXT)
- image_url (TEXT)
- in_stock (INTEGER)

## Pages

1. **Home** (`/`) - Landing page with hero section and category links
2. **Catalog** (`/catalog`) - Browse all products with category filters
3. **Product Detail** (`/product/<id>`) - Individual product page with add to cart

## Sample Products

The database is pre-populated with 10 sample products across 4 categories:
- Pizza (3 items)
- Burgers (3 items)
- Pasta (2 items)
- Salads (2 items)

## Customization

- **Colors**: Edit CSS variables in `templates/base.html`
- **Products**: Modify sample products in `app.py` `init_db()` function
- **Categories**: Add new categories by inserting products with new category names

## Notes

- The database is automatically created on first run
- Cart functionality is a simple alert (not fully implemented)
- Images are from Unsplash and require internet connection
