#!/usr/bin/env python3
"""
Migration Runner Script
Automatically applies database migrations to keep schema up to date
"""
import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("psycopg2 not available. Install with: pip install psycopg2-binary")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Migration settings
MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"
DATABASE_URL = os.getenv("DATABASE_URL")

# Migration tracking table
MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    checksum TEXT
);
"""


class MigrationRunner:
    """Handles database migration execution"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.migrations_dir = MIGRATIONS_DIR
        
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.database_url)
    
    def ensure_migration_table(self):
        """Create migration tracking table if it doesn't exist"""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(MIGRATION_TABLE_SQL)
            conn.commit()
            cur.close()
            logger.info("Migration tracking table ready")
        finally:
            conn.close()
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of already applied migrations"""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT filename FROM schema_migrations ORDER BY filename")
            applied = [row[0] for row in cur.fetchall()]
            cur.close()
            return applied
        finally:
            conn.close()
    
    def get_pending_migrations(self) -> List[Path]:
        """Get list of migrations that need to be applied"""
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {self.migrations_dir}")
            return []
        
        # Get all .sql files
        all_migrations = sorted([f for f in self.migrations_dir.glob("*.sql")])
        applied_migrations = set(self.get_applied_migrations())
        
        pending = [m for m in all_migrations if m.name not in applied_migrations]
        return pending
    
    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate simple checksum for migration file"""
        import hashlib
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def apply_migration(self, migration_file: Path) -> bool:
        """Apply a single migration file"""
        logger.info(f"Applying migration: {migration_file.name}")
        
        try:
            # Read migration content
            with open(migration_file, 'r', encoding='utf-8') as f:
                migration_sql = f.read()
            
            # Calculate checksum
            checksum = self.calculate_checksum(migration_file)
            
            # Apply migration
            conn = self.get_connection()
            try:
                cur = conn.cursor()
                
                # Execute migration SQL
                cur.execute(migration_sql)
                
                # Record migration
                cur.execute("""
                    INSERT INTO schema_migrations (filename, checksum)
                    VALUES (%s, %s)
                """, (migration_file.name, checksum))
                
                conn.commit()
                cur.close()
                
                logger.info(f"✅ Successfully applied: {migration_file.name}")
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"❌ Failed to apply {migration_file.name}: {e}")
                return False
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error reading migration file {migration_file.name}: {e}")
            return False
    
    def run_migrations(self, dry_run: bool = False) -> Dict[str, Any]:
        """Run all pending migrations"""
        logger.info("🚀 Starting migration process...")
        
        if not self.database_url:
            logger.error("❌ DATABASE_URL not set")
            return {"success": False, "error": "DATABASE_URL not configured"}
        
        try:
            # Test database connection
            conn = self.get_connection()
            conn.close()
            logger.info("✅ Database connection successful")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return {"success": False, "error": f"Database connection failed: {e}"}
        
        # Ensure migration table exists
        try:
            self.ensure_migration_table()
        except Exception as e:
            logger.error(f"❌ Failed to create migration table: {e}")
            return {"success": False, "error": f"Migration table creation failed: {e}"}
        
        # Get pending migrations
        pending_migrations = self.get_pending_migrations()
        
        if not pending_migrations:
            logger.info("✅ No pending migrations")
            return {"success": True, "applied": [], "message": "No migrations to apply"}
        
        logger.info(f"Found {len(pending_migrations)} pending migrations")
        
        if dry_run:
            logger.info("🔍 DRY RUN - Would apply:")
            for migration in pending_migrations:
                logger.info(f"  - {migration.name}")
            return {"success": True, "dry_run": True, "pending": [m.name for m in pending_migrations]}
        
        # Apply migrations
        applied = []
        failed = []
        
        for migration in pending_migrations:
            if self.apply_migration(migration):
                applied.append(migration.name)
            else:
                failed.append(migration.name)
                break  # Stop on first failure
        
        result = {
            "success": len(failed) == 0,
            "applied": applied,
            "failed": failed,
            "total_pending": len(pending_migrations)
        }
        
        if result["success"]:
            logger.info(f"🎉 Successfully applied {len(applied)} migrations")
        else:
            logger.error(f"❌ Migration failed. Applied: {len(applied)}, Failed: {len(failed)}")
        
        return result
    
    def rollback_last_migration(self) -> Dict[str, Any]:
        """Rollback the last applied migration (if rollback SQL is available)"""
        logger.warning("⚠️  Migration rollback not implemented yet")
        return {"success": False, "error": "Rollback not implemented"}
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status"""
        try:
            applied = self.get_applied_migrations()
            pending = self.get_pending_migrations()
            
            return {
                "database_url": self.database_url[:50] + "..." if len(self.database_url) > 50 else self.database_url,
                "applied_count": len(applied),
                "pending_count": len(pending),
                "applied_migrations": applied,
                "pending_migrations": [m.name for m in pending],
                "last_applied": applied[-1] if applied else None
            }
        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return {"error": str(e)}


def main():
    """Main CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database Migration Runner")
    parser.add_argument("--dry-run", action="store_true", help="Show pending migrations without applying")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--database-url", help="Database URL (overrides env var)")
    
    args = parser.parse_args()
    
    # Get database URL
    db_url = args.database_url or DATABASE_URL
    if not db_url:
        print("❌ Error: DATABASE_URL not set")
        print("Set via environment variable or --database-url flag")
        print("Example: DATABASE_URL='postgres://user:pass@localhost:5432/dbname'")
        sys.exit(1)
    
    # Create runner
    runner = MigrationRunner(db_url)
    
    if args.status:
        # Show status
        print("📊 Migration Status:")
        print("=" * 50)
        status = runner.get_migration_status()
        
        if "error" in status:
            print(f"❌ Error: {status['error']}")
            sys.exit(1)
        
        print(f"Database: {status['database_url']}")
        print(f"Applied migrations: {status['applied_count']}")
        print(f"Pending migrations: {status['pending_count']}")
        
        if status['applied_migrations']:
            print("\n✅ Applied:")
            for migration in status['applied_migrations']:
                print(f"  - {migration}")
        
        if status['pending_migrations']:
            print("\n⏳ Pending:")
            for migration in status['pending_migrations']:
                print(f"  - {migration}")
        
        if status['last_applied']:
            print(f"\n🕐 Last applied: {status['last_applied']}")
        
    else:
        # Run migrations
        result = runner.run_migrations(dry_run=args.dry_run)
        
        if not result["success"]:
            print(f"❌ Migration failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
        
        if args.dry_run:
            print("🔍 Dry run completed successfully")
        else:
            print("🎉 Migrations completed successfully")


if __name__ == "__main__":
    main()