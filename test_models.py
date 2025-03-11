"""
Test script to verify that models can be imported without circular dependency issues.
"""
from app.models import TenantDB, OrganizationDB, TenantOrganizationDB

def test_models():
    """Test that models can be imported without circular dependency issues."""
    print("TenantDB:", TenantDB)
    print("OrganizationDB:", OrganizationDB)
    print("TenantOrganizationDB:", TenantOrganizationDB)
    print("All models imported successfully!")

if __name__ == "__main__":
    test_models() 