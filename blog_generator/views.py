from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings

from .models import BlogPost
import json
import os
import validators
from pytube import YouTube


from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import YoutubeLoader, UnstructuredURLLoader


@login_required
def index(request):
    return render(request, 'index.html')


@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            yt_link = data['link']
            groq_api_key = os.getenv("GROQ_API_KEY")

            if not yt_link or not groq_api_key:
                return JsonResponse({'error': 'Missing YouTube link or API key'}, status=400)

            if not validators.url(yt_link):
                return JsonResponse({'error': 'Invalid URL'}, status=400)

            title = yt_title(yt_link)
            summary = generate_blog_from_youtube(yt_link, groq_api_key)
            if not summary:
                return JsonResponse({'error': "Failed to generate blog article"}, status=500)


            new_blog_article = BlogPost.objects.create(
                user=request.user,
                youtube_title=title,
                youtube_link=yt_link,
                generated_content=summary,
            )

            new_blog_article.save()

            return JsonResponse({'content':summary})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


def yt_title(link):
    try:
        loader = YoutubeLoader.from_youtube_url(link, add_video_info=True)
        docs = loader.load()
        if hasattr(docs[0].metadata, 'title'):
            return docs[0].metadata['title']
        return 'YouTube Video'
    except Exception as e:
        print("Failed to get title:", e)
        return 'YouTube Video'
    

# def yt_title(link):
#     yt = YouTube(link)
#     title = yt.title
#     return title


def generate_blog_from_youtube(link, api_key):
    try:
        loader = YoutubeLoader.from_youtube_url(link, add_video_info=False)
        docs = loader.load()

        llm = ChatGroq(model="Gemma2-9b-It", groq_api_key=api_key)
        prompt = PromptTemplate.from_template(
            """You are a professional content writer. Write a high-quality, engaging, and SEO-optimized blog article based on the following transcript of a YouTube video.

        Use the following guidelines:
        - Title the blog appropriately.
        - Write a strong introduction that hooks the reader.
        - Convert the spoken content into well-structured written paragraphs.
        - Use headings and subheadings where appropriate.
        - Summarize key points and provide insightful takeaways.
        - Make the tone natural, informative, and reader-friendly.
        - Avoid repeating phrases from the transcript verbatim unless quoting.

        TRANSCRIPT:
        {text}

        BLOG ARTICLE:"""
        )

        chain = load_summarize_chain(llm, chain_type="stuff", prompt=prompt)

        output_summary = chain.run(docs)

        return output_summary

    except Exception as e:
        print("Summarization error:", str(e))
        return "Failed to generate summary."


def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, 'all-blogs.html', {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail':blog_article_detail})
    else:
        return redirect('/')


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})

    return render(request, 'login.html')


def user_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        repeat_password = request.POST.get('repeatPassword')

        if password != repeat_password:
            return render(request, 'signup.html', {'error_message': 'Passwords do not match'})

        try:
            if User.objects.filter(username=username).exists():
                return render(request, 'signup.html', {'error_message': 'Username already exists'})
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            return redirect('/')
        except Exception as e:
            return render(request, 'signup.html', {'error_message': f'Error creating account: {e}'})

    return render(request, 'signup.html')


def user_logout(request):
    logout(request)
    return redirect('/')