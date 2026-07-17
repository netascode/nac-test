{# iterate_list_chunked fmc.domains name domain_name objects.hosts 2 #}
*** Settings ***
Documentation   Test1

*** Test Cases ***
{% for domain in fmc.domains | default([]) %}
{% if domain.name == domain_name %}

Test {{ domain.name }}

{% for host in domain.objects.hosts | default([]) %}

Test {{ domain.name }} Host {{ host.name }}
    Should Be Equal   {{ host.ip }}   {{ host.ip }}
{% endfor %}

{% for net in domain.objects.networks | default([]) %}

Test {{ domain.name }} Network {{ net.name }}
    Should Be Equal   {{ net.cidr }}   {{ net.cidr }}
{% endfor %}

{% endif %}
{% endfor %}