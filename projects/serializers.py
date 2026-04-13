from rest_framework import serializers

from .models import Project, ProjectPhoto


class ProjectPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPhoto
        fields = '__all__'

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'
