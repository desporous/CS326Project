from django import forms
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse, Http404
from django.views import generic
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.decorators import permission_required, login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.views.generic.edit import CreateView, UpdateView, DeleteView

from datetime import datetime, timezone
import json

from .models import UserProfile, Trip, Comment, Notification
from .forms import *


def index(request):
	num_users = UserProfile.objects.all().count()
	num_trips = Trip.objects.all().count()
	num_admins = UserProfile.objects.filter(admin_level__exact='a').count()
	
	return render(
		request,
		'index.html',
		context={'num_users': num_users, 'num_trips': num_trips, 'num_admins': num_admins}
	)


def register(request):
	if request.user.is_anonymous:
		pass
	else:
		raise PermissionDenied("You cannot register while logged in!")

	if request.method == 'POST':
		form = RegisterForm(request.POST)
		
		if form.is_valid():
			form.save()
			username = form.cleaned_data.get('username')
			raw_password = form.cleaned_data.get('password1')
			user = authenticate(username=username, password=raw_password)
			
			# create and save corresponding user profile
			userpro = UserProfile(user=user, first_name=form.cleaned_data.get('first_name'), last_name=form.cleaned_data.get('last_name'), email=form.cleaned_data.get('email'))
			userpro.save()
			
			# create a welcome notification
			Notification(recipient=userpro, message='Welcome to UMOC! Click here to fill out your profile', link=reverse('profile')).save()
			
			login(request, user)
			return redirect('dashboard')
	
	else:
		form = RegisterForm()
	
	return render(request, 'register.html', {'form': form})


@login_required
def profile(request):
	user = request.user
	profile = user.profile
	
	if request.method == 'POST':
		form = UpdateProfileForm(request.POST, request.FILES)
		
		if form.is_valid():
			user.first_name = form.cleaned_data['first_name']
			user.last_name = form.cleaned_data['last_name']
			user.email = form.cleaned_data['email']
			user.save()
			
			profile.first_name = form.cleaned_data['first_name']
			profile.last_name = form.cleaned_data['last_name']
			profile.email = form.cleaned_data['email']
			profile.dob = form.cleaned_data['date_of_birth']
			profile.phone_num = form.cleaned_data['phone_number']
			profile.profile_img = form.cleaned_data['profile_image']
			profile.contact_name = form.cleaned_data['contact_name']
			profile.contact_phone = form.cleaned_data['contact_number']
			profile.save()
			
			return HttpResponseRedirect(reverse('dashboard'))
			
	else:
		form = UpdateProfileForm(initial={'first_name': profile.first_name,
										  'last_name': profile.last_name,
										  'email': profile.email,
										  'date_of_birth': profile.dob,
										  'phone_number': profile.phone_num,
										  'contact_name': profile.contact_name,
										  'contact_number': profile.contact_phone})

	return render(request, 'profile.html', {'form': form})


@login_required
def waiver(request):
	user = request.user
	profile = user.profile
	
	if profile.dob and profile.phone_num and profile.contact_name and profile.contact_phone:
		pass
	else:
		raise PermissionDenied("You must first fill out your profile page!")
	
	if request.method == 'POST':
		form = WaiverForm(request.POST, profile=profile)
		
		if form.is_valid():
			profile.can_join_trip = True
			profile.save()
			
			return redirect('dashboard')
			
	else:
		form = WaiverForm(initial={'first_name': profile.first_name,
									'last_name': profile.last_name,
									'current_date': datetime.now().date()})
	
	return render(request, 'waiver.html', {'form': form})


def dashboard(request):
	""" 
	Renders page with menu of upcoming trips, in order of start time.
	"""
	# filter trips by those starting after current time, and order by start time
	return render(request, 'dashboard.html', {'trips': Trip.objects.filter(start_time__gte=datetime.now(timezone.utc)).order_by('start_time')})

		
def trip_info(request, pk):
	"""
	Info page for a trip. Allows users to sign up, withdraw, and comment. Trip's leader and admins can edit or cancel the trip.
	"""
	try:
		return render(
			request,
			'trip_info.html',
			context={'trip': Trip.objects.get(pk=pk)}
		)
	except Trip.DoesNotExist:
		raise Http404('Sorry! That trip does not exist')

	
def public_profile(request, pk):
	try:
		return render(
			request,
			'public_profile.html',
			context={'profile': UserProfile.objects.get(pk=pk)}
		)
	except UserProfile.DoesNotExist:
		raise Http404("UserProfile does not exist")


class ProcessedComment:
	# initialize with a Comment var
	def __init__(self, comment, parent=None):
		self.id = comment.id
		self.author = comment.author
		self.text = comment.text
		self.time_stamp = comment.time_stamp
		self.depth = comment.depth
		self.href = comment.author.get_absolute_url()
		self.replies = []
		self.parent = parent
		
	# Unravels child comments and threads, running recursively and returning a list of ordered comments. Sets depth for each. 
	def unravel(self):
		ordered = [self]
		for comment in self.replies:
			# comment.depth = self.depth + 1
			ordered += comment.unravel()
		return ordered
		
	def get_padding(self):
		return self.depth * 30
		
	def __repr__(self):
		return 'ProcessedComment(id="{}", author="{}", text="{}", time_stamp="{}". {} replies'.format(self.id, self.author, self.text, self.time_stamp, len(self.replies))


def trip_comments(request, pk):
	""" 
	Manages comments for a trip of given id (/trip/<id>/comments). Only available via AJAX on properly authenticated users.
	GET: Renders HTML comment section for given trip
	POST: Creates the added comment. Requires a 'text' field storing the text body of the comment and a 'parent' field storing the id of the comment the new comment is replying to (0 if none). Returns 'success': boolean and 'message': string (will be empty if success=True) 
	"""
	if request.method == 'GET':
		print ('Retrieving comments for trip id {}'.format(pk))
		# TODO: CHECK IF TRIP IS IN DATABASE
		
		# map id->ProcessedComment
		processed_comments = {}
		# top-level comments
		top_level_comments = []
		
		# retrieve comments on given trip in order of posting
		trip_comments = Comment.objects.filter(trip_id=pk).order_by('time_stamp')

		for comment in trip_comments:
			# create ProcessedComment wrapper and add to dictionary
			processed = ProcessedComment(comment)
			print (processed.href)
			processed_comments[comment.id] = processed
			
			if comment.parent:
				# set comment's parent and add comment as reply to parent
				processed.parent = processed_comments[comment.parent.id]
				processed_comments[comment.parent.id].replies.append(processed)
			else:
				# comment must be top-level
				top_level_comments.append(processed)
				
		# unravel top-level comments, creating list of ordered ProcessedComments
		ordered_comments = []
		for processed_comment in top_level_comments:
			ordered_comments += processed_comment.unravel()
			
		return render(
			request,
			'trip_comments.html',
			context={'comments': ordered_comments}
		)
		#return JsonResponse(data, safe=False)
	elif request.method == 'POST' and request.user.is_authenticated: # and request.is_ajax()
		print('Saving new comment by {}'.format(request.user.profile))
		print (request.POST)
		# TODO: COULD BE A VULNERABILITY (NOT ENOUGH DATA VALIDATION)
		
		# retrieve relevant database records
		author = UserProfile.objects.get(pk=request.user.profile.id)
		parent_comment = Comment.objects.get(pk=request.POST['parent']) if request.POST['parent'] != '0' else None
		trip = Trip.objects.get(pk=pk)
		
		# enforce maximumum depth of 6?
		
		# create Comment object and save to database
		comment = Comment(author=author, parent=parent_comment, text=request.POST['text'], trip=trip, depth=parent_comment.depth + 1 if parent_comment else 0)
		comment.save()
		
		# create Notification for comment's parent if one exists and author is not equal to current signed-in user
		if parent_comment and request.user.profile.id != parent_comment.author.id:
			Notification(recipient=parent_comment.author, message='{} {} replied to your comment'.format(author.first_name, author.last_name), link=comment.get_absolute_url()).save()
		# no parent: create notification for trip leader 
		elif not parent_comment and request.user.profile.id != trip.leader.id:
			Notification(recipient=trip.leader, message='{} {} commented on one of your trips'.format(author.first_name, author.last_name), link=comment.get_absolute_url()).save()
		
		# return rendered comment
		return render(
			request, 
			'trip_comments.html', 
			context={'comments': [ProcessedComment(comment)]}
		)
		#return JsonResponse({'success': True})
	else:
		raise Http404('Access Denied')


@login_required
def notifications(request):
	"""
	AJAX handler managing currently signed in user's notifications. Only accessible via AJAX requests. Returns rendered HTML of user's notifications, for insertion into the navbar on GET. POST accepts 'dismissed_id': <int:id> as the id of the notification the user has dismissed. 
	"""
	if request.method == 'GET':
		print ('Retrieving notifications for user {}'.format(request.user.id))
		return render(
			request,
			'notifications.html',
			context={'notifications': Notification.objects.filter(recipient_id=request.user.profile.id, dismissed=False).order_by('-time_stamp')}
		)
	elif request.method == 'POST':
		print ('Received request to dismiss notification {}'.format(request.POST))
		requested = Notification.objects.get(pk=request.POST['dismissed_id'])
		print (requested)
		requested.dismissed = True
		requested.save()
		print (requested)
		return JsonResponse({'success': True})
	else:
		raise Http404('Access Denied')
		

@login_required
def admin_management(request):
	"""
	Allows an administrator to set user permission levels. IMPORTANT: This must only be accessible by admins. admin_edit is used to make AJAX calls to receive and update specific user data.
	"""
	if request.user.profile.admin_level != 'a':
		raise Http404('You do not have access to this page')
	else:
		return render(
			request,
			'admin_management.html',
			context={'users': UserProfile.objects.all().order_by('last_name')}
		)


@login_required
def admin_edit(request):
	"""
	Manages AJAX calls for the admin page. IMPORTANT: This must only be accessible by admins. Run AJAX GET 'user_id': <id> to retrieve JSON data for a specific user. Run AJAX POST 'user_id': <id>, 'admin_level': <a/l/u> to set admin level for the specified user.
	"""
	if request.user.profile.admin_level != 'a':
		raise Http404('You do not have access to this page')
	elif request.method == 'GET':
		print ('Received GET {}'.format(request.GET))
		try:
			user = UserProfile.objects.get(pk=request.GET['user_id'])
			return JsonResponse({'id': user.id, 'first_name': user.first_name, 'last_name': user.last_name, 'href': user.get_absolute_url(), 'email': user.email, 'admin_level': user.admin_level })
		except UserProfile.DoesNotExist:
			return JsonResponse({'success': False})  # todo: return error
	elif request.method == 'POST':
		print ('Received POST {}'.format(request.POST))
		try:
			user = UserProfile.objects.get(pk=request.POST['user_id'])
			user.admin_level = request.POST['admin_level'];
			user.save();
			print('Set {} to {}'.format(user, user.admin_level))
			
			# send user a notification
			Notification(recipient=user, message='Your admin level was set to {}'.format({'a': 'Admin', 'l': 'Leader', 'u': 'User'}[user.admin_level])).save()
			return JsonResponse({'success': True});
		except UserProfile.DoesNotExist:
			return JsonResponse({'success': False})  # todo: return error
		return JsonResponse({'success': True})
	else:
		raise Http404("This url is not being used correctly")


class TripCreate(CreateView):
	model = Trip
	fields = ('name', 'description', 'capacity', 'start_time', 'end_time', 'tag', 'leader')
	template_name = 'umoc/trip_form.html'

	def get(self, request):
		form = AdminTripForm()
		return render(request, self.template_name, {'form': form})

	def post(self, request):
		if request.method == 'POST':
			form = AdminTripForm(request.POST)
			if form.is_valid():
				trip_instance = form.save(commit=False)
				trip_instance.num_seats = form.cleaned_data['capacity']
				trip_instance.save()
				return HttpResponseRedirect(reverse('dashboard'))
		
		else:
			form = AdminTripForm()

		return render(request, self.template_name, {'form': form})


class TripUpdate(UpdateView):
	model = Trip
	fields = ('name', 'description', 'capacity', 'start_time', 'end_time', 'tag', 'leader')
	template_name = 'umoc/trip_form.html'
		
	def get(self, request, pk):
		trip_instance = Trip.objects.get(pk=pk)
		form = AdminUpdateTripForm(initial={'name': trip_instance.name,
									  'description': trip_instance.description,
									  'capacity': trip_instance.capacity,
									  'start_time': trip_instance.start_time.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime('%Y-%m-%d %I:%M %p'),
									  'end_time': trip_instance.end_time.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime('%Y-%m-%d %I:%M %p'),
									  'tag': trip_instance.tag,
									  'leader': trip_instance.leader})
		
		return render(request, self.template_name, {'form': form})
		
	def post(self, request, pk):
		if request.method == 'POST':
			trip = Trip.objects.get(pk=pk)
			form = AdminUpdateTripForm(request.POST, trip=trip)
			
			if form.is_valid():
				trip.name = form.cleaned_data['name']
				trip.description = form.cleaned_data['description']
				trip.num_seats = trip.num_seats - trip.capacity + form.cleaned_data['capacity']
				trip.capacity = form.cleaned_data['capacity']
				trip.start_time = form.cleaned_data['start_time']
				trip.end_time = form.cleaned_data['end_time']
				trip.tag = form.cleaned_data['tag']
				trip.leader = form.cleaned_data['leader']
				trip.save()
				return HttpResponseRedirect(reverse('dashboard'))
		
		else:
			form = get(self, request, pk)

		return render(request, self.template_name, {'form': form})


class TripDelete(DeleteView):
    model = Trip
    success_url = reverse_lazy('dashboard')

@login_required
def cancel_trip(request, pk):
	""" 
	Cancels trip of the given id. Requires requesting user to be trip leader or an admin. Returns 404 if the trip is over or has already been canceled. Creates notification for each user who had been signed up to participate.
	"""
	try:
		trip = Trip.objects.get(pk=pk)
		if trip.is_over():
			raise Http404("You can't cancel a trip that is over")
		elif request.user.profile.admin_level != 'a' and request.user.profile != trip.leader:
			raise Http404("You do not have permission")
		else:  # success
			trip.cancelled = True
			trip.save()
			
			# create notifications
			for participant in trip.participants.all():
				Notification(recipient=participant, message='{} was cancelled'.format(trip.name), link=trip.get_absolute_url()).save()
				
			return redirect('trip_info', pk=pk)
	except Trip.DoesNotExist:
		raise Http404('Sorry, that trip does not exist')

		
@login_required
def join_trip(request, pk):
	"""
	Adds user to specified trip. Trip must exist and have capacity for another user, and user must not already be signed up. Returns 404 if this is not the case (it shouldn't be). Sends user a notification and reloads trip page on success. 
	"""
	try:
		trip = Trip.objects.get(pk=pk)
		if trip.is_over():
			raise Http404("You can't join a trip that is over")
		elif request.user.profile in trip.participants.all():
			raise Http404('You are already signed up!')
		elif not trip.num_seats:
			raise Http404('This trip is full')
		else:  # success
			trip.participants.add(request.user.profile)
			trip.num_seats -= 1
			trip.save()
			
			# create notification
			Notification(recipient=request.user.profile, message='You joined {} successfully!'.format(trip.name), link=trip.get_absolute_url()).save()
			
			return redirect('trip_info', pk=pk)
	except Trip.DoesNotExist:
		raise Http404('Sorry, that trip does not exist')
	

@login_required	
def leave_trip(request, pk):
	"""
	Removes user from specified trip. Trip must exist and have capacity for another user, and user must not already be signed up. Returns 404 if this is not the case (it shouldn't be). Reloads trip page on success.
	"""
	try:
		trip = Trip.objects.get(pk=pk)
		if trip.is_over():
			raise Http404("You can't leave a trip that is over")
		elif request.user.profile not in trip.participants.all():
			raise Http404("You aren't signed up for this trip")
		elif request.user.profile == trip.leader:
			raise Http404("You're the leader, you can't leave! You must cancel the trip or have an admin switch you out.")
		else:  # success
			trip.participants.remove(request.user.profile)
			trip.num_seats += 1
			trip.save()
			return redirect('trip_info', pk=pk)
	except Trip.DoesNotExist:
		raise Http404('Sorry, that trip does not exist')
		

@login_required
def trip_report(request, pk):
	"""
	Generates a report on the given trip: Includes signed up users, with emergency information, along with other things. Only accessible for the trip leader, and any admins. Returns 404 if this is not the case.
	"""
	try:
		trip = Trip.objects.get(pk=pk)
		if request.user.profile.admin_level != 'a' and request.user.profile != trip.leader:
			raise Http404("You do not have permission to view this page.")
		else:  # success
			return render(request, 'trip_report.html', context={'trip': trip})
	except Trip.DoesNotExist:
		raise Http404('Sorry, that trip does not exist')
		
	
def all_trips(request):
	"""
	Renders dashboard page, but with all trips that have ever happened from newest to oldest.
	"""
	return render(request, 'dashboard.html', {'trips': Trip.objects.all().order_by('-start_time')})