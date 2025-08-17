from app import db
from sqlalchemy.sql import func
from sqlalchemy.types import JSON
import json

class Link(db.Model):
    __tablename__ = "links"

    id = db.Column(db.String(36), primary_key=True)  # UUID or short link
    link = db.Column(db.String(2048), nullable=False)
    total_redirect = db.Column(db.Integer, default=0)

    stats = db.relationship(
        "Stat",
        backref="link_obj",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Link id={self.id} link={self.link}>"


class Stat(db.Model):
    __tablename__ = "stats"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    link = db.Column(db.String, db.ForeignKey("links.id"), nullable=False, index=True)
    at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    country = db.Column(db.String(2), index=True)  # ISO country code

    # Column name is still "metadata", but in Python we use "meta"
    meta = db.Column("metadata", JSON, nullable=True)

    def __repr__(self):
        return f"<Stat id={self.id} link={self.link} country={self.country} meta={self.meta}>"

    # ---------------------------
    # VALIDATOR for safe JSON
    # ---------------------------
    @staticmethod
    def validate_metadata(data):
        """
        Ensures metadata is JSON-serializable and only contains safe datatypes:
        dict, list, str, int, float, bool, None.
        """
        def check_types(value):
            if isinstance(value, (str, int, float, bool)) or value is None:
                return True
            if isinstance(value, dict):
                return all(check_types(v) for v in value.values())
            if isinstance(value, list):
                return all(check_types(v) for v in value)
            return False  # reject other types (like objects, SQL, functions)

        if not check_types(data):
            raise ValueError("Invalid metadata: contains unsafe datatypes")

        # Test JSON serialization (ensures safe storage)
        try:
            json.dumps(data)
        except (TypeError, ValueError):
            raise ValueError("Invalid metadata: not JSON serializable")

        return data

    # Hook to validate automatically before insert/update
    @db.validates("meta")
    def validate_json(self, key, value):
        return self.validate_metadata(value)
