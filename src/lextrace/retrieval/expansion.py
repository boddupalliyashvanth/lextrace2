from pathlib import Path

import yaml


class QueryExpander:
    def __init__(self, map_path: str = "data/statute_map.yaml"):
        self.map_path = Path(map_path)
        self.alias_map: dict[str, str] = {}
        self._load()

    def _load(self):
        if not self.map_path.exists():
            return
            
        with open(self.map_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not data:
                return
            
            # The mapping MUST have provenance according to user constraints
            for entry in data.get("mappings", []):
                if "provenance" not in entry:
                    continue # Ignore mappings without provenance
                
                canonical = entry.get("canonical")
                aliases = entry.get("aliases", [])
                
                if canonical:
                    for alias in aliases:
                        # naive lowercasing for expansion
                        self.alias_map[alias.lower()] = canonical

    def expand(self, query: str) -> str:
        if not self.alias_map:
            return query
            
        expanded_query = query
        query_lower = query.lower()
        
        import re
        for alias, canonical in self.alias_map.items():
            # Use regex for word boundaries to avoid partial matches
            pattern = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
            if pattern.search(query_lower):
                if canonical.lower() not in query_lower:
                    expanded_query += f" {canonical}"
                    
        return expanded_query
