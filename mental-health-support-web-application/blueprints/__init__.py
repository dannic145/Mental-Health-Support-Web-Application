from .peacepal import peacepal_app  # Import the Blueprint from peacepal.py

# Expose the Blueprint so it can be imported and registered in the main app
__all__ = ['peacepal_app']