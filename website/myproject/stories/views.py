from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from django.core.paginator import Paginator
from .models import EmbeddedArticles, Clusters, Publisher


def get_bias_statistics(articles, total_articles):

    counts = {
        'far_left': 0, 'left': 0, 'lean_left': 0,
        'center': 0,
        'lean_right': 0, 'right': 0, 'far_right': 0
    }

    for article in articles:
        if article.publisher and article.publisher.bias is not None:
            bias = float(article.publisher.bias)
            if bias <= 0.15:
                counts['far_left'] += 1
            elif bias <= 0.30:
                counts['left'] += 1
            elif bias <= 0.45:
                counts['lean_left'] += 1
            elif bias <= 0.55:
                counts['center'] += 1
            elif bias <= 0.70:
                counts['lean_right'] += 1
            elif bias <= 0.85:
                counts['right'] += 1
            else:
                counts['far_right'] += 1

    total_left = counts['far_left'] + counts['left'] + counts['lean_left']
    total_right = counts['lean_right'] + counts['right'] + counts['far_right']
    center = counts['center']

    stats = {
        "total": total_articles,
        "far_left_count": counts['far_left'],
        "left_count": counts['left'],
        "lean_left_count": counts['lean_left'],
        "center_count": center,
        "lean_right_count": counts['lean_right'],
        "right_count": counts['right'],
        "far_right_count": counts['far_right'],
        "total_left": total_left,
        "total_right": total_right,
    }

    if total_articles > 0:
        stats.update({
            "far_left_percent": int((counts['far_left'] / total_articles) * 100),
            "left_percent": int((counts['left'] / total_articles) * 100),
            "lean_left_percent": int((counts['lean_left'] / total_articles) * 100),
            "center_percent": int((center / total_articles) * 100),
            "lean_right_percent": int((counts['lean_right'] / total_articles) * 100),
            "right_percent": int((counts['right'] / total_articles) * 100),
            "far_right_percent": int((counts['far_right'] / total_articles) * 100),

            "macro_left_percent": int((total_left / total_articles) * 100),
            "macro_center_percent": int((center / total_articles) * 100),
            "macro_right_percent": int((total_right / total_articles) * 100),
        })
    else:
        stats.update({
            "far_left_percent": 0, "left_percent": 0, "lean_left_percent": 0,
            "center_percent": 0, "lean_right_percent": 0, "right_percent": 0, "far_right_percent": 0,
            "macro_left_percent": 0, "macro_center_percent": 0, "macro_right_percent": 0,
        })

    return stats



def view_event(request, id):
    cluster = get_object_or_404(Clusters, id=id)
    articles = cluster.embeddedarticles_set.select_related('publisher').all()

    print(cluster.tags)

    stats = get_bias_statistics(articles, articles.count())

    blind_spot_msg = None
    if stats["total"] >= 3:
        if stats["total_right"] == 0 and (stats["total_left"] > 0 or stats["center_count"] > 0):
            blind_spot_msg = "Zauważyliśmy, że ten temat jest niemal całkowicie ignorowany przez media prawicowe, podczas gdy centrum i lewica publikują na jego temat intensywnie."
        elif stats["total_left"] == 0 and (stats["total_right"] > 0 or stats["center_count"] > 0):
            blind_spot_msg = "Zauważyliśmy, że ten temat jest niemal całkowicie ignorowany przez media lewicowe, podczas gdy centrum i prawica mocno go eksploatują."
        elif stats["center_count"] == 0 and stats["total_left"] > 0 and stats["total_right"] > 0:
            blind_spot_msg = "Temat ten silnie polaryzuje. Piszą o nim media skrajne z obu stron, podczas gdy media centrowe głównego nurtu w ogóle go nie poruszają."

    context = {
        "cluster": cluster,
        "articles": articles,
        "stats": stats,
        "blind_spot_msg": blind_spot_msg
    }

    return render(request, "stories/view_event.html", context)



def index(request):
    clusters_to_show = []

    clusters = EmbeddedArticles.objects.defer('centroid').values(
        'cluster_id', 'cluster__updated_at', 'cluster__title'
    ).annotate(
        articles_per_cluster=Count('id')
    ).order_by('-cluster__created_at')

    for cluster in clusters:
        num_of_occurences = cluster['articles_per_cluster']

        if num_of_occurences >= 5:
            single_id_cluster = cluster['cluster_id']
            cluster_ai_title = cluster['cluster__title']

            articles_with_given_cluster_id = EmbeddedArticles.objects.defer('embedding').filter(
                cluster_id=single_id_cluster).select_related('publisher')

            stats = get_bias_statistics(articles_with_given_cluster_id, num_of_occurences)

            source_set = set()
            cluster_articles = []

            for article in articles_with_given_cluster_id:
                if article.source not in source_set:
                    cluster_articles.append({
                        "source": article.source,
                        "url": article.url,
                        "title": article.title,
                    })
                    source_set.add(article.source)

            if len(source_set) <= 1:
                continue

            clusters_to_show.append({
                "cluster_id": single_id_cluster,
                "updated_at": cluster['cluster__updated_at'],
                "articles": cluster_articles,
                "cluster_ai_title": cluster_ai_title,
                "left_percent": stats["macro_left_percent"],
                "center_percent": stats["macro_center_percent"],
                "right_percent": stats["macro_right_percent"],
            })

    paginator = Paginator(clusters_to_show, 4)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }

    return render(request, 'stories/index.html', context)