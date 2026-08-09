
from django.db import models

class Publisher(models.Model):
    id = models.BigAutoField(primary_key=True)
    bias = models.FloatField(null=True)
    name= models.CharField(max_length=30, null=False)
    domain = models.CharField(max_length=100, null=True)
    logo = models.URLField(blank=True, null=True)


class Clusters(models.Model):
    id = models.BigAutoField(primary_key=True)
    centroid = models.TextField(blank=True, null=True)  # This field type is a guess.
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    title = models.TextField(max_length=50, null=True, blank=True)
    ai_summary = models.TextField(max_length=500, null=True)

    class Meta:
        db_table = 'clusters'


class EmbeddedArticles(models.Model):
    id = models.BigAutoField(primary_key=True)
    cluster = models.ForeignKey(Clusters, models.DO_NOTHING, blank=True, null=True)
    publisher = models.ForeignKey(
        Publisher, on_delete=models.CASCADE,
        related_name='articles',
        null=True
    )

    article_description = models.TextField(max_length=500, null=True)
    title = models.TextField(blank=True, null=True)
    url = models.TextField(unique=True, blank=True, null=True)
    source = models.TextField(blank=True, null=True)
    embedding = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'embedded_articles'



