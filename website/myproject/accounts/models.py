from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.


class User(AbstractUser):

    # birth_date = models.DateField(null=False, blank=True)
    pass

from django.db import models

class Person(models.Model):
    name = models.CharField(max_length=200, help_text="Imię i nazwisko kanoniczne, np. Donald Tusk")
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

class PersonAlias(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='aliases')
    alias = models.CharField(max_length=200, db_index=True)

    class Meta:
        verbose_name_plural = "Aliases"

    def __str__(self):
        return f"{self.alias} -> {self.person.name}"