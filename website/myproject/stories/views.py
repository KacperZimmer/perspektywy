from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from django.core.paginator import Paginator
from .models import EmbeddedArticles, Clusters, Publisher

from django.shortcuts import render, get_object_or_404
from .models import Clusters


def view_event(request, id):
    cluster = get_object_or_404(Clusters, id=id)

    articles = cluster.embeddedarticles_set.select_related('publisher').all()
    total_articles = articles.count()

    # 1. Inicjalizacja liczników dla 7 poziomów
    far_left_count = 0
    left_count = 0
    lean_left_count = 0
    center_count = 0
    lean_right_count = 0
    right_count = 0
    far_right_count = 0

    # 2. Iteracja i kategoryzacja na 7 przedziałów
    for article in articles:
        if article.publisher and article.publisher.bias is not None:
            bias = float(article.publisher.bias)

            if bias <= 0.15:
                far_left_count += 1
            elif bias <= 0.30:
                left_count += 1
            elif bias <= 0.45:
                lean_left_count += 1
            elif bias <= 0.55:
                center_count += 1
            elif bias <= 0.70:
                lean_right_count += 1
            elif bias <= 0.85:
                right_count += 1
            else:
                far_right_count += 1

    # 3. Obliczanie procentów dla wszystkich 7 poziomów
    if total_articles > 0:
        far_left_percent = int((far_left_count / total_articles) * 100)
        left_percent = int((left_count / total_articles) * 100)
        lean_left_percent = int((lean_left_count / total_articles) * 100)
        center_percent = int((center_count / total_articles) * 100)
        lean_right_percent = int((lean_right_count / total_articles) * 100)
        right_percent = int((right_count / total_articles) * 100)
        far_right_percent = int((far_right_count / total_articles) * 100)
    else:
        far_left_percent = left_percent = lean_left_percent = center_percent = \
            lean_right_percent = right_percent = far_right_percent = 0

    # 4. Agregacja (makro-kategorie) potrzebna do analizy "Martwych Pól"
    total_left = far_left_count + left_count + lean_left_count
    total_right = lean_right_count + right_count + far_right_count

    blind_spot_msg = None
    if total_articles >= 3:
        if total_right == 0 and (total_left > 0 or center_count > 0):
            blind_spot_msg = "Zauważyliśmy, że ten temat jest niemal całkowicie ignorowany przez media prawicowe, podczas gdy centrum i lewica publikują na jego temat intensywnie."
        elif total_left == 0 and (total_right > 0 or center_count > 0):
            blind_spot_msg = "Zauważyliśmy, że ten temat jest niemal całkowicie ignorowany przez media lewicowe, podczas gdy centrum i prawica mocno go eksploatują."
        elif center_count == 0 and total_left > 0 and total_right > 0:
            blind_spot_msg = "Temat ten silnie polaryzuje. Piszą o nim media skrajne z obu stron, podczas gdy media centrowe głównego nurtu w ogóle go nie poruszają."

    context = {
        "cluster": cluster,
        "articles": articles,
        "stats": {
            "total": total_articles,

            "far_left_percent": far_left_percent,
            "left_percent": left_percent,
            "lean_left_percent": lean_left_percent,
            "center_percent": center_percent,
            "lean_right_percent": lean_right_percent,
            "right_percent": right_percent,
            "far_right_percent": far_right_percent,

            "far_left_count": far_left_count,
            "left_count": left_count,
            "lean_left_count": lean_left_count,
            "center_count": center_count,
            "lean_right_count": lean_right_count,
            "right_count": right_count,
            "far_right_count": far_right_count,

            "total_left": total_left,
            "total_right": total_right,
        },
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
                "updated_at": cluster['cluster__updated_at'],
                "articles": cluster_articles,
                "cluster_ai_title": cluster_ai_title
            })

    paginator = Paginator(clusters_to_show, 4)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }

    return render(request, 'stories/index.html', context)