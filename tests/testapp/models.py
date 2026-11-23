from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Item(models.Model):
    name = models.CharField("nombre", max_length=100)
    code = models.CharField(max_length=20, blank=True)
    active = models.BooleanField(default=True)
    created = models.DateField(null=True)
    category = models.ForeignKey(Category, null=True, on_delete=models.SET_NULL)
    tags = models.ManyToManyField(Tag, blank=True)
    owner = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name


class Note(models.Model):
    text = models.CharField(max_length=100)
