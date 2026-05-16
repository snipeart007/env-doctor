from env_doctor.database.manager import DatabaseManager
from env_doctor.database.models import CompatibilityRule
from env_doctor.utils.config import load_config
from sqlmodel import select

config = load_config()
db_path = config.get_expanded_db_path()
print(f"Checking database at: {db_path}")

db = DatabaseManager(str(db_path))
with db.get_session() as session:
    statement = select(CompatibilityRule)
    rules = session.exec(statement).all()
    print(f"Total rules: {len(rules)}")
    for r in rules:
        print(f"- {r.package_name} {r.package_version_range} vs {r.dependency_name} {r.dependency_version_range} (Severity: {r.severity})")
