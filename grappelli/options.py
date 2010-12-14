import operator

from django.contrib import admin
from django.db import models
from django.db.models.query import QuerySet
from django.http import HttpResponse, Http404
from django.utils import simplejson
from django.utils.encoding import smart_str
from grappelli.widgets import AutocompleteWidget, MultipleAutocompleteWidget


AUTOCOMPLETE_FIELDS_DEFAULTS = {
    'id': 'pk',
    'limit': 5,
    'value': lambda o: unicode(o),
    'label': lambda o: unicode(o),
}

class AutoCompleteModelAdmin(admin.ModelAdmin):
    """
    Based on http://code.djangoproject.com/ticket/14370 and 
    the changeset in it.  

    http://bitbucket.org/tyrion/django/changeset/04488ec05e92
    """
    autocomplete_fields = {}

    def __init__(self, *args, **kwargs):
        super(AutoCompleteModelAdmin, self).__init__(*args, **kwargs)

        def build_setting(value):
            if value in settings['queryset'].model._meta.get_all_field_names():
                return lambda m: getattr(m, value)
            return lambda m: value % vars(m)

        autocomplete_fields = {}
        for (field, values) in self.autocomplete_fields.items():
            settings = autocomplete_fields[field] = AUTOCOMPLETE_FIELDS_DEFAULTS.copy()
            settings.update(values)
            if hasattr(self.model, field):
                rel = getattr(self.model, field).field.rel
                settings['id'] = settings.get('id', rel.get_related_field().name)
                if not settings.get('queryset'):
                    settings['queryset'] = rel.to._default_manager.complex_filter(rel.limit_choices_to)
            for option in ('value', 'label'):
                if isinstance(settings[option], (str, unicode)):
                    settings[option] = build_setting(settings[option])

        self.autocomplete_fields = autocomplete_fields

    def get_urls(self):
        from django.conf.urls.defaults import patterns, url
        urlpatterns = patterns('',
            url(r'^autocomplete/(?P<field>[\w]+)/$',
                self.autocomplete),
        )
        return urlpatterns + super(AutoCompleteModelAdmin, self).get_urls()

    def autocomplete(self, request, field, extra_content=None):
        query = request.GET.get('term', None)
        query_by_id = request.GET.get('by_id', None) is not None

        if field not in self.autocomplete_fields or query is None:
            raise Http404

        settings = self.autocomplete_fields[field]
        queryset = settings['queryset']

        def construct_search(field_name):
            # use different lookup methods depending on the notation
            if field_name.startswith('^'):
                return "%s__istartswith" % field_name[1:]
            elif field_name.startswith('='):
                return "%s__iexact" % field_name[1:]
            elif field_name.startswith('@'):
                return "%s__search" % field_name[1:]
            else:
                return "%s__icontains" % field_name

        if query_by_id:
            # lookup only via an exact match on id
            settings['fields'] = ('=id',)

        for bit in query.split():
            or_queries = [models.Q(**{construct_search(
                            smart_str(field_name)): bit})
                          for field_name in settings['fields']]
            queryset = queryset.filter(reduce(operator.or_, or_queries))

        data = []
        for o in queryset[:settings['limit']]:
            data.append({
                    'id': getattr(o, settings['id']),
                    'value': settings['value'](o),
                    'label': settings['label'](o),
                    })
        return HttpResponse(simplejson.dumps(data))

    def formfield_for_dbfield(self, db_field, **kwargs):
        """
        Overrides the default widget for ManyToMany & ForeignKey fields 
        if they are specified in the autocomplete_fields class attribute.
        """
        db = kwargs.get('using')
        if isinstance(db_field, models.ManyToManyField) and \
                db_field.name in self.autocomplete_fields:
            kwargs['widget'] = MultipleAutocompleteWidget(
                self.autocomplete_fields[db_field.name], using=db)
            kwargs['help_text'] = ''
        elif isinstance(db_field, models.ForeignKey) and \
                db_field.name in self.autocomplete_fields:
            kwargs['widget']= AutocompleteWidget(
                self.autocomplete_fields[db_field.name], using=db)
        return super(AutoCompleteModelAdmin, self).formfield_for_dbfield(db_field, **kwargs)
