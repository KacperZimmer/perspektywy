from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.


class User(AbstractUser):

    birth_date = models.DateField(null=False, blank=True)
    