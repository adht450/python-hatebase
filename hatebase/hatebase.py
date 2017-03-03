import os
import json
import requests
import urllib
from datetime import datetime

"""
TODO:
	add __str__ and __repr__ methods to Sighting and Vocabulary classes
	improve default value handling on Sighting and Vocabulary variables
	do a lot of bug testing
"""

class API(object):	
	def __init__(self, key, timeout=300):
		self.key = key
		self.timeout = timeout
		self.version = "v3-0"
		self.limit = 100
		self.count = None
		self.last = None
		self.languages = Languages()
		self.countries = Countries()
		
	# check how many queries remain for today
	def remaining(self):
		if self.count is not None:
			return self.limit-self.count
		else:
			return self.limit
	
	# make a sighting query
	def sighting(self, vocab=None, variant_of=None, language=None, 
				 about_ethnicity=None, about_nationality=None, 
				 about_religion=None, about_gender=None, 
				 about_sexual_orientation=None, about_disability=None,
				 about_class=None, archaic=None, country=None, 
				 city_or_community=None, _type=None, start_date=None, 
				 end_date=None, page=1, limit=1):
		
		# parse filter arguments into a filter dictionary
		filters = self._parse_filter(vocab, variant_of, language, 
					 about_ethnicity, about_nationality, about_religion, 
					 about_gender, about_sexual_orientation, about_disability, 
					 about_class, archaic, page, country, city_or_community, 
					 _type, start_date, end_date)
					 
		return self._get_results(filters, 'sightings', limit)
	
	# make a vocabulary query
	def vocabulary(self, vocab=None, variant_of=None, language=None, 
				   about_ethnicity=None, about_nationality=None, 
				   about_religion=None, about_gender=None, 
				   about_sexual_orientation=None, about_disability=None,
				   about_class=None, archaic=None, page=1, limit=1):
		
		# parse filter arguments into a filter dictionary
		filters = self._parse_filter(vocab, variant_of, language, about_ethnicity, 
				     about_nationality, about_religion, about_gender, 
				     about_sexual_orientation, about_disability, about_class, 
				     archaic, page)
					 
		return self._get_results(filters, 'vocabulary', limit)
	
	# take a dictionary of filters, a query_type, and a page limit and return 
	# a list of either Vocabulary or Sighting objects depending on query_type
	def _get_results(self, filters, qtype, limit):
		qtypes = {'vocabulary': Vocabulary, 'sightings': Sighting}
	
		# parse limit argument to determine the maximum number of pages
		if limit is None or (type(limit) == int and limit < 0):
			limit = 0
		elif type(limit) != int:
			raise TypeError("limit must be an integer")

		# loop in case multiple pages are needed
		finished = False
		results = []
		while not finished:
			# construct filter string
			filter_str = '|'.join(("%s=%s"%(k,v) for k,v in filters.items()))
		
			# construct the query url
			# http://api.hatebase.org/version/key/query-type/output/encoded-filters
			url = "http://api.hatebase.org/%s/%s/%s/%s/%s"%\
				(self.version, self.key, qtype, 'json', filter_str)
			
			# make a request to this url and deal with http error response codes
			r = requests.get(url, timeout=self.timeout)
			r.raise_for_status()
			
			# convert the response into an object
			response = Response(r, qtypes[qtype])
			
			# add the results to the list
			results += response.results
			
			# update api metadata according to response
			self.count = response.number_of_queries_today
			self.last = response.timestamp
			
			# move cursor to the next page
			filters['page'] += 1
			
			# decrement limit to move termination closer if initial value > 0
			limit -= 1
			
			# check termination conditions
			if limit == 0: finished = True
			if response.number_of_queries_today >= self.limit: finished = True
			if len(results) >= response.total_results: finished = True
			
		return results
	
	# takes all API arguments and returns a dictionary of filters
	def _parse_filter(self, vocab, variant_of, language, about_ethnicity, 
				     about_nationality, about_religion, about_gender, 
				     about_sexual_orientation, about_disability,about_class, 
				     archaic, page, country=None, city_or_community=None, 
				     _type=None, start_date=None, end_date=None):

		filters = {} # dictionary of argument to value mappings
		
		# check plain text filter arguments
		textargs = {"vocabulary": vocab,
			        "variant_of": variant_of,
			        "city_or_community": city_or_community}
		for name, var in textargs.items():
			if var is not None:
				if not isinstance(var, basestring):
					raise TypeError("%s must inherit from basestring",(name,))
				else:
					filters[name] = urllib.quote(var.encode('utf8'))
		
		# check ISO standardized arguments
		isoargs = {"language": (language, self.languages.codes),
				   "country": (country, self.countries.codes)}
		for name,(var,codes) in isoargs.items():
			if var is not None:
				if not isinstance(var, basestring):
					raise TypeError("%s must inherit from basestring",(name,))
				elif var not in codes:
					raise ValueError("%s must be an ISO standard code"%(name,))
				else:
					filters[name] = var
		
		# check boolean filter arguments
		boolvars = {"about_ethnicity": about_ethnicity,
			        "about_nationality": about_nationality,
			        "about_religion": about_religion,
			        "about_gender": about_gender,
			        "about_sexual_orientation": about_sexual_orientation,
			        "about_disability": about_disability,
			        "about_class": about_class,
			        "archaic": archaic}
		for name, var in boolvars.items():
			if var is not None:
				if not var in [0, 1, False, True]:
					raise TypeError("%s must be in {0, 1, True, False}"%(name,))
				else:
					filters[name] = int(var)
				
		# verify that page is an integer (still permitting negative integers)
		if page is not None:
			if not type(page) == int:
				raise TypeError("page must be an integer")
			else:
				filters["page"] = page
				
		# verify that type is one of the permitted values
		if _type is not None:
			if not _type in ['r', 'o', 'u', 't']:
				raise TypeError("type must be in {r, o, u, t}")
			else:
				filters["type"] = _type
				
		# validate date inputs
		dateargs = {"start_date": start_date,
					"end_date": end_date}
		for name, var in dateargs.items():
			if var is not None:
				try:
					filters[name] = var.strftime(r"%Y-%m-%d")
				except:
					try:
						dt = datetime.strptime(var, r"%Y-%m-%d")
						filters[name] = dt.strftime(r"%Y-%m-%d")
					except:
						raise TypeError("unable to parse %s date"%(name,))
					
		return filters		
						

class Response(object):
	def __init__(self, r, request_type):
		# ensure this is a valid request with a successful response
		r.raise_for_status()
		
		# extract the response data and store it
		response = r.json()
		
		if 'human_readable_error' in response['errors'].keys():
			raise HateBaseError("%s error code %s"%\
			(response['errors']['human_readable_error'], \
			 response['errors']['error_code']))
		
		self.timestamp = (datetime.utcnow()-datetime(1970, 1, 1)).total_seconds()
		self.number_of_queries_today = int(response["number_of_queries_today"])
		self.total_results = int(response["number_of_results"])
		self.page_results = int(response["number_of_results_on_this_page"])
		self.page = int(response["page"])
		self.status = response["status"]
		self.version = response["version"]
		self.results = [request_type(e) for e in response["data"]["datapoint"]]
		
class Vocabulary(object):
	def __init__(self, result):
		# general data
		self.lang = result["language"]
		self.vocabulary = result["vocabulary"]
		self.meaning = result["meaning"]
		self.pronunciation = result["pronunciation"]
		self.variant_of = result["variant_of"]
		self.variants = result["variants"]
		self.offensiveness = float(result["offensiveness"])
		
		# boolean filters
		self.about_class = bool(int(result["about_class"]))
		self.about_disability = bool(int(result["about_disability"]))
		self.about_ethnicity = bool(int(result["about_ethnicity"]))
		self.about_gender = bool(int(result["about_gender"]))
		self.about_nationality = bool(int(result["about_nationality"]))
		self.about_religion = bool(int(result["about_religion"]))
		self.about_sexual_orientation = bool(int(result["about_sexual_orientation"]))
		self.archaic = bool(int(result["archaic"]))
		
		# usage data
		try: self.last_sighting = datetime.strptime(result["last_sighting"], 
											        r"%Y-%m-%d %H:%M:%S")
		except: self.last_sighting = None
		
		# count data
		try: self.citations = int(result["number_of_citations"])
		except: self.citations = 0
		try: self.revisions = int(result["number_of_revisions"])
		except: self.citations = 0
		try: self.sightings = int(result["number_of_sightings"])
		except: self.sightings = 0
		try: self.variants = int(result["number_of_variants"])
		except: self.sightings = 0
		
		
class Sighting(object):
	def __init__(self, result):
		# Sighting Specific Data
		self.id = int(result["sighting_id"])
		try: self.date = datetime.strptime(result["date"], r"%Y-%m-%d %H:%M:%S")
		except: self.date = None
		self.country = result["country"]
		self.city_or_community = result["city_or_community"]
		self.latitude = float(result["latitude"])
		self.longitude = float(result["longitude"])
		self.htype = result["human_readable_type"]
		self.type = result["type"]
		
		# general data
		self.lang = result["language"]
		self.vocabulary = result["vocabulary"]
		self.meaning = result["meaning"]
		self.pronunciation = result["pronunciation"]
		self.variant_of = result["variant_of"]
		self.variants = result["variants"]
		self.offensiveness = float(result["offensiveness"])
		
		# boolean filters
		self.about_class = bool(int(result["about_class"]))
		self.about_disability = bool(int(result["about_disability"]))
		self.about_ethnicity = bool(int(result["about_ethnicity"]))
		self.about_gender = bool(int(result["about_gender"]))
		self.about_nationality = bool(int(result["about_nationality"]))
		self.about_religion = bool(int(result["about_religion"]))
		self.about_sexual_orientation = bool(int(result["about_sexual_orientation"]))
		self.archaic = bool(int(result["archaic"]))
		

class Languages(object):
	def __init__(self):
		# determine the directory containing this script
		dir_path = os.path.dirname(os.path.realpath(__file__))
		# load the language dictionary from languages.json
		with open("%s/languages.json"%(dir_path),'r') as fin:
			languages = json.load(fin)
		# add all of these as attributes of the object
		self.__dict__.update(languages)
		# store a set of all valid codes
		self.codes = set([v for k,v in languages.items()])
		
class Countries(object):
	def __init__(self):
		# determine the directory containing this script
		dir_path = os.path.dirname(os.path.realpath(__file__))
		# load the country dictionary from countries.json
		with open("%s/countries.json"%(dir_path),'r') as fin:
			countries = json.load(fin)
		# add all of these as attributes of the object
		self.__dict__.update(countries)
		# store a set of all valid codes
		self.codes = set([v for k,v in countries.items()])

class HateBaseError(RuntimeError):
	pass