from rest_framework import serializers

from .models import *


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = "__all__"


class MemberCheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberCheckIn
        fields = "__all__"
