from rest_framework import serializers
from .models import Padron, VotoLog

class PadronSerializer(serializers.ModelSerializer):
    class Meta:
        model = Padron
        fields = '__all__'

class VotoLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = VotoLog
        fields = '__all__'
