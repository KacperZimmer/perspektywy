from django.db import models
from django.contrib.postgres.fields import ArrayField

class Entity(models.Model):

    id = models.BigAutoField(primary_key=True)
    bio = models.TextField(max_length=500, null=False)
    name = models.TextField(max_length=50, null=False)
    image = models.URLField(max_length=500, blank=True, null=True)
    popularity = models.IntegerField(default=0, null=False)
    slug = models.SlugField(max_length=150, unique=True)

class AliasEntity(models.Model):
    id = models.BigAutoField(primary_key=True)

    aliases = ArrayField(
        models.CharField(max_length=1000),
        blank=True,
        null=True
    )
    original_entity = models.ForeignKey(
        Entity, on_delete=models.CASCADE,
        related_name='alias_owner',
        null=True
    )



