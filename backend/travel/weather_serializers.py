from rest_framework import serializers


class WeatherSerializer(serializers.Serializer):
    label = serializers.CharField()
    temperature = serializers.FloatField()
    forecastAt = serializers.DateTimeField()
    issuedAt = serializers.DateTimeField()
    fetchedAt = serializers.DateTimeField()
    source = serializers.CharField()


class WeatherResponseSerializer(serializers.Serializer):
    weather = WeatherSerializer(allow_null=True)


class WeatherErrorSerializer(serializers.Serializer):
    code = serializers.CharField()


class WeatherErrorResponseSerializer(serializers.Serializer):
    weather = WeatherSerializer(allow_null=True)
    error = WeatherErrorSerializer()
