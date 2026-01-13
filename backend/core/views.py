from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from .serializers import (
    UserRegistrationSerializer, 
    CustomTokenObtainPairSerializer,
    UserProfileSerializer
)
from django.db.models import Count, Q
from .models import Game, LibraryEntry
from .serializers import GameSerializer, LibraryEntrySerializer

User = get_user_model()

# --- 1. Registration View ---
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = UserRegistrationSerializer

# --- 2. Login View ---
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# --- 3. User Profile View ---
class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        # Returns the currently logged-in user
        return self.request.user
    

class GameListView(generics.ListAPIView):
    serializer_class = GameSerializer
    permission_classes = (AllowAny,) # Publicly accessible

    def get_queryset(self):
        queryset = Game.objects.all()
        
        # A. Filtering (Genre/Platform would strictly need fields in Model, 
        # but here we search text fields for simplicity based on your doc)
        search_query = self.request.query_params.get('search', None)
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(developer__icontains=search_query) |
                Q(publisher__icontains=search_query)
            )

        # B. Trending Logic (Wireframe Requirement)
        # Sort by number of library entries (popularity)
        trending = self.request.query_params.get('trending', None)
        if trending == 'true':
            queryset = queryset.annotate(
                popularity=Count('library_entries')
            ).order_by('-popularity')
            
        return queryset

# --- 5. Library Management View (Page 16) ---
class LibraryEntryCreateView(generics.ListCreateAPIView):
    serializer_class = LibraryEntrySerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        # Return only the current user's library
        return LibraryEntry.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically associate the entry with the logged-in user
        serializer.save(user=self.request.user)

# --- 6. Library Detail View (Update/Delete) ---
class LibraryEntryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LibraryEntrySerializer
    permission_classes = (IsAuthenticated,)
    
    def get_queryset(self):
        # Ensure users can only edit/delete their own entries
        return LibraryEntry.objects.filter(user=self.request.user)
    
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView # Using APIView for custom transaction logic
from rest_framework import status
from .models import Review

# ... existing views ...

# --- 7. Create Review View (Atomic Transaction - Snippet-04) ---
class ReviewCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        data = request.data
        user = request.user
        game_id = data.get('game_id') or data.get('game') # Handle both inputs

        # 1. Validation before transaction
        if not game_id:
            return Response({"error": "Game ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 2. ATOMIC BLOCK (The Core Logic)
            with transaction.atomic():
                # Check for existing review (Locking logic implied)
                if Review.objects.filter(user=user, game_id=game_id).exists():
                    raise ValueError("You have already reviewed this game.")

                # Create the review
                review = Review.objects.create(
                    user=user,
                    game_id=game_id,
                    rating=data['rating'],
                    comment=data.get('comment', '')
                )

                # 3. Trigger Game Update
                game = Game.objects.get(id=game_id)
                game.update_average_rating()

                return Response({
                    "success": True, 
                    "data": {"id": review.id, "rating": review.rating}
                }, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

