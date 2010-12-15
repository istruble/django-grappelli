from django import forms
from django.conf import settings
from django.forms.util import flatatt
from django.utils import simplejson
from django.utils.safestring import mark_safe
from django.utils.text import truncate_words

#from django.utils.html import escape

class AutocompleteWidget(forms.Widget):
    class Media:
        css = {
            'all': ( 
                settings.ADMIN_MEDIA_PREFIX+'css/jquery-ui-grappelli-extensions.css',
                ),
        }
        js = (
            settings.ADMIN_MEDIA_PREFIX+'js/admin/autocomplete.js',
        )

    def __init__(self, settings, attrs=None, using=None, **js_options):
        self.settings = settings
        self.db = using
        self.js_options = {
            'source': settings.get('source'),
            'multiple': settings.get('multiple', False),
            'force_selection': settings.get('force_selection', True),
            }
        self.js_options.update(js_options)
        super(AutocompleteWidget, self).__init__(attrs)

    def get_autocomplete_url(self, name):
        return '../autocomplete/%s/' % name

    def render(self, name, value, attrs=None, hattrs=None, initial_objects=u''):
        if value is None:
            value = ''
        hidden_id = 'id_hidden_%s' % name
        hidden_attrs = self.build_attrs(type='hidden', name=name, value=value, id=hidden_id)
        normal_attrs = self.build_attrs(attrs, type='text')
        if value:
            normal_attrs['value'] = self.label_for_value(value)
        if not self.js_options.get('source'):
            self.js_options['source'] = self.get_autocomplete_url(name)
        options = simplejson.dumps(self.js_options)
        return mark_safe(u'\n'.join((
            u'<input%s />\n' % flatatt(hidden_attrs),
            u'<input%s />\n' % flatatt(normal_attrs),
            initial_objects,
            u'<script type="text/javascript">',
            u'django.jQuery("#id_%s").djangoautocomplete(%s);' % (name, options),
            u'</script>\n',
            )))

    def label_for_value(self, value):
        qs, key, value_fmt = [self.settings[k] for k in ('queryset', 'id', 'value')]
        try:
            obj = qs.get(**{key: value})
            return value_fmt(obj)
        except qs.model.DoesNotExist:
            # should never happen.
            return value

class MultipleAutocompleteWidget(AutocompleteWidget):

    def __init__(self, settings, attrs=None, using=None, **js_options):
        js_options['multiple'] = True
        super(MultipleAutocompleteWidget, self).__init__(settings, attrs,
            using, **js_options)

    def render(self, name, value, attrs=None, hattrs=None):
        if value:
            initial_objects = self.initial_objects(value)
            value = ','.join([str(v) for v in value])
        else:
            initial_objects = u''
        return super(MultipleAutocompleteWidget, self).render(name, value, 
            attrs, hattrs, initial_objects)

    def label_for_value(self, value):
        return ''

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if value:
            return value.split(',')
        return value

    def initial_objects(self, value):
        qs, key, label_fmt = [self.settings[k] for k in ('queryset','id','label')]
        output = [u'<ul class="ui-autocomplete-values">']
        for obj in qs.filter(**{'%s__in' % key: value}):
            output.append(u'<li>%s</li>' % label_fmt(obj))
        output.append(u'</ul>\n')
        return mark_safe(u'\n'.join(output))
