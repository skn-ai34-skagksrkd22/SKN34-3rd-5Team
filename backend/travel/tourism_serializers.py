import math

from rest_framework import serializers

from .tourism_provider import CONTENT_TYPES, RADIUS, STADIUMS, distance_meters


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not hasattr(data, "keys"):
            raise serializers.ValidationError("객체를 입력해 주세요.")
        unknown = set(data.keys()) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({name: "지원하지 않는 필드입니다." for name in sorted(unknown)})
        return super().to_internal_value(data)


class FiniteFloatField(serializers.FloatField):
    def __init__(self, *args, strict=False, **kwargs):
        self.strict = strict
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        if isinstance(data, bool) or self.strict and not isinstance(data, (int, float)):
            raise serializers.ValidationError("유한한 숫자를 입력해 주세요.")
        value = super().to_internal_value(data)
        if not math.isfinite(value):
            raise serializers.ValidationError("유한한 숫자를 입력해 주세요.")
        return value


class StringChoiceField(serializers.ChoiceField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid_choice", input=data)
        return super().to_internal_value(data)


class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if not isinstance(data, int) or isinstance(data, bool):
            raise serializers.ValidationError("정수를 입력해 주세요.")
        return super().to_internal_value(data)


class StrictCharField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError("문자열을 입력해 주세요.")
        return super().to_internal_value(data)


class HttpsUrlField(serializers.URLField):
    def to_internal_value(self, data):
        if data == "":
            return ""
        value = super().to_internal_value(data)
        if not value.startswith("https://"):
            raise serializers.ValidationError("HTTPS URL만 입력해 주세요.")
        return value


class TourismQuerySerializer(StrictSerializer):
    stadium = StringChoiceField(choices=tuple(STADIUMS))
    lat = FiniteFloatField(min_value=-90, max_value=90)
    lng = FiniteFloatField(min_value=-180, max_value=180)

    def validate(self, attrs):
        _, _, lat, lng = STADIUMS[attrs["stadium"]]
        if distance_meters(lat, lng, attrs["lat"], attrs["lng"]) > 1000:
            raise serializers.ValidationError("구장 위치를 확인해 주세요.")
        return attrs


class ProviderPlaceSerializer(StrictSerializer):
    placeId = serializers.RegexField(r"^tour:\d+$", max_length=260)
    tourContentId = serializers.RegexField(r"^\d+$", max_length=255)
    contentTypeId = StringChoiceField(choices=CONTENT_TYPES)
    name = StrictCharField(max_length=255, trim_whitespace=True)
    lat = FiniteFloatField(strict=True, min_value=-90, max_value=90)
    lng = FiniteFloatField(strict=True, min_value=-180, max_value=180)
    category = StringChoiceField(choices=("산책", "관광 명소", "실내 놀거리"))
    kind = StringChoiceField(choices=("walk", "sight", "indoor"))
    cuisine = StringChoiceField(choices=("기타",))
    address = StrictCharField(max_length=500, allow_blank=True)
    phone = StrictCharField(max_length=120, allow_blank=True)
    detail = StrictCharField(max_length=500)
    distance = FiniteFloatField(strict=True, min_value=0, max_value=RADIUS)
    subcategory = StrictCharField(max_length=120, required=False)
    imageUrl = HttpsUrlField(max_length=500, required=False, allow_blank=True)
    sourceUrl = HttpsUrlField(max_length=500, required=False, allow_blank=True)

    def validate(self, attrs):
        category = {"walk": "산책", "sight": "관광 명소", "indoor": "실내 놀거리"}[attrs["kind"]]
        if attrs["placeId"] != f'tour:{attrs["tourContentId"]}' or attrs["category"] != category:
            raise serializers.ValidationError("장소 ID 또는 분류가 일치하지 않습니다.")
        return attrs


class TourismPlaceWriteSerializer(StrictSerializer):
    contentId = serializers.RegexField(r"^\d+$", max_length=255)
    contentType = StringChoiceField(choices=CONTENT_TYPES)
    name = StrictCharField(max_length=255, trim_whitespace=True)
    category = StringChoiceField(choices=("walk", "sight", "indoor"))
    address = StrictCharField(max_length=500, required=False, allow_blank=True)
    lat = FiniteFloatField(strict=True, min_value=-90, max_value=90)
    lng = FiniteFloatField(strict=True, min_value=-180, max_value=180)
    phone = StrictCharField(max_length=120, required=False, allow_blank=True)
    imageUrl = HttpsUrlField(max_length=500, required=False, allow_blank=True)
    sourceUrl = HttpsUrlField(max_length=500, required=False, allow_blank=True)


class TourismPlaceListSerializer(StrictSerializer):
    page = StrictIntegerField(min_value=1, required=False, default=1)
    pageSize = StrictIntegerField(min_value=1, max_value=100, required=False, default=20)
    q = StrictCharField(max_length=120, required=False, allow_blank=True, default="")
    category = StringChoiceField(choices=("walk", "sight", "indoor"), required=False)
    minLat = FiniteFloatField(strict=True, min_value=-90, max_value=90, required=False)
    maxLat = FiniteFloatField(strict=True, min_value=-90, max_value=90, required=False)
    minLng = FiniteFloatField(strict=True, min_value=-180, max_value=180, required=False)
    maxLng = FiniteFloatField(strict=True, min_value=-180, max_value=180, required=False)

    def validate(self, attrs):
        if attrs.get("minLat", -90) > attrs.get("maxLat", 90) or attrs.get("minLng", -180) > attrs.get("maxLng", 180):
            raise serializers.ValidationError("위치 범위의 최솟값과 최댓값을 확인해 주세요.")
        return attrs


class TourismResponseSerializer(serializers.Serializer):
    status = StringChoiceField(choices=("ok", "partial", "unconfigured", "error"))
    places = ProviderPlaceSerializer(many=True)
    truncated = serializers.BooleanField()
    stale = serializers.BooleanField(required=False)
    fetchedAt = serializers.DateTimeField(allow_null=True, required=False)
    lastSyncedAt = serializers.DateTimeField(allow_null=True, required=False)
