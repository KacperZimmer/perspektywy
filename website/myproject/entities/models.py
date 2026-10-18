from django.db import models


class Entity(models.Model):

    id = models.BigAutoField(primary_key=True)
    bio = models.TextField(max_length=500, null=False)
    name = models.TextField(max_length=50, null=False)
    image = models.URLField(max_length=500, blank=True, null=True)
    popularity = models.IntegerField(default=0, null=False)
    slug = models.SlugField(max_length=150, unique=True)

