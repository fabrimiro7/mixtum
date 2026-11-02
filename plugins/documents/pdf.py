from rest_framework.exceptions import ValidationError


def validate_area(area):
    if not isinstance(area, dict) or set(area) != {"x", "y", "width", "height"}:
        raise ValidationError("L'area deve contenere x, y, width e height normalizzati.")
    try:
        x, y, width, height = (float(area[key]) for key in ("x", "y", "width", "height"))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Coordinate area non numeriche.") from exc
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
        raise ValidationError("Area fuori dalla pagina o priva di dimensione.")
    return {"x": x, "y": y, "width": width, "height": height}


def _fitz():
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise ValidationError("PyMuPDF non è installato nel pacchetto Documents.") from exc
    return fitz


def _open_pdf(fitz, source):
    return fitz.open(stream=source, filetype="pdf") if isinstance(source, (bytes, bytearray)) else fitz.open(source)


def inspect_pdf(source):
    fitz = _fitz()
    try:
        with _open_pdf(fitz, source) as document:
            if document.needs_pass:
                raise ValidationError("PDF protetto da password non supportato.")
            return document.page_count
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("PDF non valido o non leggibile.") from exc


def extract_pdf(source, *, pages=None, area=None, batch_size=20):
    fitz = _fitz()
    normalized_area = validate_area(area) if area is not None else None
    try:
        with _open_pdf(fitz, source) as document:
            if document.needs_pass:
                raise ValidationError("PDF protetto da password non supportato.")
            if pages is None:
                selected = list(range(document.page_count))
            else:
                requested = list(pages)
                if not requested or any(
                    not isinstance(page, int) or page < 1 or page > document.page_count for page in requested
                ):
                    raise ValidationError("Selezione pagine non valida.")
                selected = [page - 1 for page in requested]
            for offset in range(0, len(selected), batch_size):
                for page_index in selected[offset:offset + batch_size]:
                    page = document.load_page(page_index)
                    clip = None
                    if normalized_area is not None:
                        rect = page.rect
                        clip = fitz.Rect(
                            rect.x0 + rect.width * normalized_area["x"],
                            rect.y0 + rect.height * normalized_area["y"],
                            rect.x0 + rect.width * (normalized_area["x"] + normalized_area["width"]),
                            rect.y0 + rect.height * (normalized_area["y"] + normalized_area["height"]),
                        )
                    text = page.get_text("text", clip=clip).strip()
                    yield {
                        "text": text, "page": page_index + 1, "area": normalized_area,
                        "metadata": {},
                    }
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("Impossibile elaborare il PDF richiesto.") from exc


def render_pdf_page(source, page_number, *, max_width=1600):
    fitz = _fitz()
    try:
        with _open_pdf(fitz, source) as document:
            if not isinstance(page_number, int) or page_number < 1 or page_number > document.page_count:
                raise ValidationError("Pagina non valida.")
            page = document.load_page(page_number - 1)
            scale = min(max_width / max(page.rect.width, 1), 3.0)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            return pixmap.tobytes("png")
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("Impossibile visualizzare la pagina PDF.") from exc
