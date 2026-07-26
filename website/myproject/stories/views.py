from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from django.core.paginator import Paginator
from .models import EmbeddedArticles, Clusters


def view_event(request, id):
    cluster = get_object_or_404(Clusters, id=id)
    context = {
        "cluster": cluster
    }
    return render(request, "stories/view_event.html", context)


def index(request):
    clusters_to_show = []
    clusters = EmbeddedArticles.objects.values('cluster_id').annotate(
        articles_per_cluster=Count('id')
    )

    for cluster in clusters:
        num_of_occurences = cluster['articles_per_cluster']
        if num_of_occurences >= 5:
            single_id_cluster = cluster['cluster_id']
            articles_with_given_cluster_id = EmbeddedArticles.objects.defer('embedding').filter(
                cluster_id=single_id_cluster)

            cluster_articles = []
            for article in articles_with_given_cluster_id:
                cluster_articles.append({
                    "source": article.source,
                    "url": article.url,
                    "title": article.title,
                })

            clusters_to_show.append({
                "cluster_id": single_id_cluster,
                "articles": cluster_articles
            })

    paginator = Paginator(clusters_to_show, 4)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }

    return render(request, 'stories/index.html', context)