from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from django.core.paginator import Paginator
from .models import EmbeddedArticles, Clusters, Publisher

from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from django.core.paginator import Paginator
from .models import EmbeddedArticles, Clusters, Publisher


def view_event(request, id):
    cluster = get_object_or_404(Clusters, id=id)

    articles = cluster.embeddedarticles_set.select_related('publisher').all()

    total_articles = articles.count()


    left_count = 0
    center_count = 0
    right_count = 0

    for article in articles:
        if article.publisher and article.publisher.bias is not None:
            bias = float(article.publisher.bias)

            if bias <= 0.35:
                left_count += 1
            elif bias <= 0.60:
                center_count += 1
            else:
                right_count += 1

    if total_articles > 0:
        left_percent = int((left_count / total_articles) * 100)
        center_percent = int((center_count / total_articles) * 100)
        right_percent = int((right_count / total_articles) * 100)
    else:
        left_percent = center_percent = right_percent = 0

    blind_spot_msg = None
    if total_articles >= 3:
        if right_count == 0 and (left_count > 0 or center_count > 0):
            blind_spot_msg = "Zauważyliśmy, że ten temat jest niemal całkowicie ignorowany przez media prawicowe, podczas gdy centrum i lewica publikują na jego temat intensywnie."
        elif left_count == 0 and (right_count > 0 or center_count > 0):
            blind_spot_msg = "Zauważyliśmy, że ten temat jest niemal całkowicie ignorowany przez media lewicowe, podczas gdy centrum i prawica mocno go eksploatują."
        elif center_count == 0 and left_count > 0 and right_count > 0:
            blind_spot_msg = "Temat ten silnie polaryzuje. Piszą o nim media skrajne z obu stron, podczas gdy media centrowe głównego nurtu w ogóle go nie poruszają."

    context = {
        "cluster": cluster,
        "articles": articles,
        "stats": {
            "total": total_articles,
            "left_percent": left_percent,
            "center_percent": center_percent,
            "right_percent": right_percent,
            "left_count": left_count,
            "center_count": center_count,
            "right_count": right_count,
        },
        "blind_spot_msg": blind_spot_msg
    }

    return render(request, "stories/view_event.html", context)


def index(request):


    clusters_to_show = []
    clusters = EmbeddedArticles.objects.defer('centroid').values('cluster_id').annotate(
        articles_per_cluster=Count('id')
    )






    for cluster in clusters:
        num_of_occurences = cluster['articles_per_cluster']
        if num_of_occurences >= 5:
            single_id_cluster = cluster['cluster_id']
            articles_with_given_cluster_id = EmbeddedArticles.objects.defer('embedding').filter(
                cluster_id=single_id_cluster)

            source_set = set()



            cluster_articles = []

            for article in articles_with_given_cluster_id:
                source_set.add(article.source)

            if len(source_set) <= 1:
                continue

            source_set = set()
            for article in articles_with_given_cluster_id:

                if article.source not in source_set:
                    cluster_articles.append({
                        "source": article.source,
                        "url": article.url,
                        "title": article.title,
                    })


                source_set.add(article.source)

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