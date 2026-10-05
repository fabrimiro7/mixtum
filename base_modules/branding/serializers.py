import re

from rest_framework import serializers
from .models import BrandingSettings
from .constants import ALLOWED_COLOR_KEYS


MAX_BRANDING_IMAGE_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/webp", "image/x-icon", "image/vnd.microsoft.icon",
}
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
RGBA_COLOR = re.compile(
    r"rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(0(?:\.\d+)?|1(?:\.0+)?)\s*\)"
)


def _valid_color(value):
    if HEX_COLOR.fullmatch(value):
        return True
    match = RGBA_COLOR.fullmatch(value)
    return bool(match and all(int(channel) <= 255 for channel in match.groups()[:3]))


def _validate_image(value):
    if value is None:
        return value
    if value.size > MAX_BRANDING_IMAGE_BYTES:
        raise serializers.ValidationError("L'immagine non può superare 2 MiB.")
    content_type = getattr(value, "content_type", "")
    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise serializers.ValidationError("Formato immagine non consentito: usare PNG, JPEG, WebP o ICO.")
    return value


class BrandingSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrandingSettings
        fields = [
            "id",
            "workspace",
            "colors",
            "logo_full",
            "logo_compact",
            "favicon",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "workspace"]

    def validate_colors(self, value):
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("colors deve essere un oggetto JSON.")

        invalid_keys = [k for k in value.keys() if k not in ALLOWED_COLOR_KEYS]
        if invalid_keys:
            raise serializers.ValidationError(f"Chiavi non consentite: {', '.join(invalid_keys)}")

        for k, v in value.items():
            if v is not None and (not isinstance(v, str) or not _valid_color(v)):
                raise serializers.ValidationError(f"Valore non valido per {k}.")

        return value

    def validate_logo_full(self, value):
        return _validate_image(value)

    def validate_logo_compact(self, value):
        return _validate_image(value)

    def validate_favicon(self, value):
        return _validate_image(value)

    def _merge_colors(self, current, incoming):
        current = current or {}
        incoming = incoming or {}
        merged = {**current}
        for key, val in incoming.items():
            if val is None:
                merged.pop(key, None)
            else:
                merged[key] = val
        return merged

    def create(self, validated_data):
        if "colors" in validated_data:
            validated_data["colors"] = self._merge_colors({}, validated_data.get("colors"))
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "colors" in validated_data:
            instance.colors = self._merge_colors(instance.colors or {}, validated_data.get("colors"))
            validated_data.pop("colors", None)
        return super().update(instance, validated_data)
