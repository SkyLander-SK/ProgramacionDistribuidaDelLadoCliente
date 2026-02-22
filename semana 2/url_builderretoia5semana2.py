from urllib.parse import quote, urlencode, urljoin
import uuid

class URLBuilder:
    """
    Construye URLs seguras para el cliente EcoMarket.
    Usa solo urllib.parse (biblioteca estándar).
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/") + "/"

    def _validate_id(self, value):
        # Permite int o UUID
        if isinstance(value, int):
            return str(value)
        try:
            uuid.UUID(str(value))
            return str(value)
        except Exception:
            raise ValueError(f"ID inválido: {value}. Debe ser int o UUID válido.")

    def build_path(self, *segments):
        """
        Construye una URL escapando caracteres peligrosos en path params.
        """
        safe_segments = []
        for seg in segments:
            if isinstance(seg, (int, str)):
                seg = str(seg)
            seg = self._validate_id(seg) if seg.isdigit() or '-' in seg else seg
            safe_segments.append(quote(seg, safe=""))
        path = "/".join(safe_segments)
        return urljoin(self.base_url, path)

    def build_url(self, path_segments=None, query_params=None):
        """
        Construye URL completa con query string seguro.
        """
        path_segments = path_segments or []
        query_params = query_params or {}

        url = self.build_path(*path_segments)
        if query_params:
            query = urlencode(query_params, doseq=True, safe="")
            url = f"{url}?{query}"
        return url