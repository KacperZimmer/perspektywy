from django.shortcuts import render
from django.db.models import Count
from django.core.paginator import Paginator  # <--- IMPORT PAGINATORA
from .models import EmbeddedArticles


def index(request):
    clusters_to_show = []
    clusters = EmbeddedArticles.objects.values('cluster_id').annotate(
        articles_per_cluster=Count('id')
    )

    for cluster in clusters:
        num_of_occurences = cluster['articles_per_cluster']
        cluster_to_append = []
        if num_of_occurences >= 5:
            single_id_cluster = cluster['cluster_id']
            articles_with_given_cluster_id = EmbeddedArticles.objects.defer('embedding').filter(
                cluster_id=single_id_cluster)

            for article in articles_with_given_cluster_id:
                cluster_to_append.append({
                    "source": article.source,
                    "url": article.url,
                    "title": article.title,
                })
            clusters_to_show.append(cluster_to_append)

    paginator = Paginator(clusters_to_show, 4)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }



    return render(request, 'stories/index.html', context)