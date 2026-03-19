*** Settings ***
Documentation     Verify Fabric Multicast Configurations in Catalyst Center
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   multicast   site_specific

*** Test Cases ***

Get Fabric Sites Data
    ${fabric_sites}=   Get Cached Fabric Sites Data
    Set Suite Variable   ${fabric_sites}

{% for fabric_site in catalyst_center.fabric.fabric_sites | default([]) %}
{% if fabric_site.multicast is defined and fabric_site.multicast.virtual_networks is defined %}
{% for vn in fabric_site.multicast.virtual_networks %}
Verify Multicast for {{ fabric_site.name }} - {{ vn.name }}
    # Check if this site should be skipped based on MANAGED_SITES
    ${should_skip}=   Should Skip Site Validation   {{ fabric_site.name }}
    Pass Execution If   ${should_skip}   Multicast for site {{ fabric_site.name }} not managed by this deployment state - skipping validation

    # Step 1: Get site ID from Sites API
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='{{ fabric_site.name }}')]
    ${site_exists}=   Evaluate   len(${site_data}) > 0
    Run Keyword If   not ${site_exists}   Fail   Site {{ fabric_site.name }} not found in Catalyst Center - deployment issue

    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    Log To Console   Site ID for {{ fabric_site.name }}: ${site_id}
    
    # Step 2: Get fabric site ID from Fabric Sites API
    ${fabric_site_data}=   Get Value From Json   ${fabric_sites.json()}   $.response[?(@.siteId=='${site_id}')]
    Run Keyword If   not ${fabric_site_data}   Fail   Fabric site with siteId ${site_id} not found in Fabric Sites API response
    ${fabric_site_entry}=   Set Variable   ${fabric_site_data}[0]
    ${fabric_site_id}=   Get From Dictionary   ${fabric_site_entry}   id
    Log To Console   Fabric site ID: ${fabric_site_id}
    
    # Get multicast configuration for this virtual network
    ${r}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/multicast/virtualNetworks?fabricId=${fabric_site_id}&virtualNetworkName={{ vn.name }}
    Log   Multicast API Response: ${r.json()}
    
    # Validate that multicast configuration exists
    ${multicast_data}=   Get Value From Json   ${r.json()}   $.response[?(@.virtualNetworkName=='{{ vn.name }}')]
    Run Keyword If   not ${multicast_data}   Fail   Multicast configuration for VN {{ vn.name }} not found
    ${multicast_entry}=   Set Variable   ${multicast_data}[0]
    
    # Validate basic multicast attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${multicast_entry}   $.virtualNetworkName   {{ vn.name }}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${multicast_entry}   $.ipPoolName   {{ vn.ip_pool_name }}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${multicast_entry}   $.fabricId   ${fabric_site_id}
    
    # Validate IPv4 SSM ranges
    {% if vn.ipv4_ssm_ranges is defined and vn.ipv4_ssm_ranges | length > 0 %}
    ${rec_ipv4_ssm_ranges}=   Get Value From Json   ${multicast_entry}   $.ipv4SsmRanges
    ${exp_ipv4_ssm_ranges}=   Create List{% for range in vn.ipv4_ssm_ranges %}   {{ range }}{% endfor %}

    Lists Should Be Equal   ${rec_ipv4_ssm_ranges}[0]   ${exp_ipv4_ssm_ranges}   ignore_order=True   msg=IPv4 SSM ranges mismatch
    {% endif %}
    
    # Validate IPv6 SSM ranges
    {% if vn.ipv6_ssm_ranges is defined and vn.ipv6_ssm_ranges | length > 0 %}
    ${rec_ipv6_ssm_ranges}=   Get Value From Json   ${multicast_entry}   $.ipv6SsmRanges
    ${exp_ipv6_ssm_ranges}=   Create List{% for range in vn.ipv6_ssm_ranges %}   {{ range }}{% endfor %}

    Lists Should Be Equal   ${rec_ipv6_ssm_ranges}[0]   ${exp_ipv6_ssm_ranges}   ignore_order=True   msg=IPv6 SSM ranges mismatch
    {% endif %}
    
    # Validate Multicast RPs
    {% if vn.multicast_rps is defined and vn.multicast_rps | length > 0 %}
    ${multicast_rps}=   Get Value From Json   ${multicast_entry}   $.multicastRPs
    ${rp_count}=   Get Length   ${multicast_rps}
    Should Be Equal As Numbers   ${rp_count}   {{ vn.multicast_rps | length }}   msg=Multicast RP count mismatch
    
    {% for rp in vn.multicast_rps %}
    # Validate RP: {{ rp.name }}
    Log   Validating Multicast RP: {{ rp.name }}
    
    # Find the RP entry by location first
    ${rp_candidates}=   Get Value From Json   ${multicast_entry}   $.multicastRPs[?(@.rpDeviceLocation=='{{ rp.rp_location }}')]
    Run Keyword If   not ${rp_candidates}   Fail   No {{ rp.rp_location }} RP found in API response
    
    # For EXTERNAL RPs with specific addresses, find the matching one
    {% if rp.rp_location == 'EXTERNAL' %}
    {% if rp.ipv4_address is defined %}
    ${rp_entry}=   Set Variable   ${None}
    FOR   ${candidate}   IN   @{rp_candidates}
        ${candidate_ipv4}=   Get From Dictionary   ${candidate}   ipv4Address
        IF   '${candidate_ipv4}' == '{{ rp.ipv4_address }}'
            ${rp_entry}=   Set Variable   ${candidate}
            BREAK
        END
    END
    Run Keyword If   ${rp_entry} == ${None}   Fail   EXTERNAL RP with IPv4 address {{ rp.ipv4_address }} not found
    {% elif rp.ipv6_address is defined %}
    ${rp_entry}=   Set Variable   ${None}
    FOR   ${candidate}   IN   @{rp_candidates}
        ${candidate_ipv6}=   Get From Dictionary   ${candidate}   ipv6Address
        IF   '${candidate_ipv6}' == '{{ rp.ipv6_address }}'
            ${rp_entry}=   Set Variable   ${candidate}
            BREAK
        END
    END
    Run Keyword If   ${rp_entry} == ${None}   Fail   EXTERNAL RP with IPv6 address {{ rp.ipv6_address }} not found
    {% else %}
    ${rp_entry}=   Set Variable   ${rp_candidates}[0]
    {% endif %}
    {% else %}
    # For FABRIC RPs, just use the first (and typically only) one
    ${rp_entry}=   Set Variable   ${rp_candidates}[0]
    {% endif %}
    
    # Validate RP location
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${rp_entry}   $.rpDeviceLocation   {{ rp.rp_location }}
    
    # Validate RP addresses (for EXTERNAL RPs, these are user-provided; for FABRIC RPs, they're auto-allocated)
    {% if rp.rp_location == 'EXTERNAL' %}
    {% if rp.ipv4_address is defined %}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${rp_entry}   $.ipv4Address   {{ rp.ipv4_address }}
    {% endif %}
    {% if rp.ipv6_address is defined %}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${rp_entry}   $.ipv6Address   {{ rp.ipv6_address }}
    {% endif %}
    {% else %}
    # For FABRIC RPs, just verify that addresses are allocated (not null)
    ${ipv4_address}=   Get Value From Json   ${rp_entry}   $.ipv4Address
    Run Keyword If   ${ipv4_address} == [None]   Log   IPv4 address not allocated for fabric RP   WARN
    ...   ELSE   Log   Fabric RP IPv4 address: ${ipv4_address}[0]
    {% endif %}
    
    # Validate default RP flags
    {% if rp.is_default_v4_rp is defined %}
    Run Keyword And Continue On Failure   Should Be Equal Value Json Boolean   ${rp_entry}   $.isDefaultV4RP   {{ rp.is_default_v4_rp }}
    {% endif %}
    {% if rp.is_default_v6_rp is defined %}
    Run Keyword And Continue On Failure   Should Be Equal Value Json Boolean   ${rp_entry}   $.isDefaultV6RP   {{ rp.is_default_v6_rp }}
    {% endif %}
    
    # Validate fabric RP devices
    {% if rp.rp_location == 'FABRIC' and rp.fabric_rps is defined and rp.fabric_rps | length > 0 %}
    ${network_device_ids_result}=   Get Value From Json   ${rp_entry}   $.networkDeviceIds
    ${network_device_ids}=   Set Variable   ${network_device_ids_result}[0]
    ${device_count}=   Get Length   ${network_device_ids}
    Should Be Equal As Numbers   ${device_count}   {{ rp.fabric_rps | length }}   msg=Fabric RP device count mismatch
    
    # Get network devices to map device names to IDs
    ${devices}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/network-device
    {% for device_name in rp.fabric_rps %}
    # Try to find device by exact hostname match first
    ${device_data}=   Get Value From Json   ${devices.json()}   $.response[?(@.hostname=='{{ device_name }}')]
    # If not found, try matching by hostname prefix (before first dot)
    IF   not ${device_data}
        ${all_devices}=   Get From Dictionary   ${devices.json()}   response
        ${device_data}=   Create List
        FOR   ${device}   IN   @{all_devices}
            ${hostname}=   Get From Dictionary   ${device}   hostname
            ${short_hostname}=   Evaluate   "${hostname}".split('.')[0]
            IF   '${short_hostname}' == '{{ device_name }}'
                Append To List   ${device_data}   ${device}
                BREAK
            END
        END
    END
    Run Keyword If   not ${device_data}   Fail   Fabric RP device {{ device_name }} not found in network devices
    ${device_id}=   Get From Dictionary   ${device_data}[0]   id
    List Should Contain Value   ${network_device_ids}   ${device_id}   msg=Device {{ device_name }} not in fabric RP network devices
    {% endfor %}
    {% endif %}
    
    # Validate IPv4 ASM ranges
    {% if rp.ipv4_asm_ranges is defined and rp.ipv4_asm_ranges | length > 0 %}
    ${rec_ipv4_asm_ranges}=   Get Value From Json   ${rp_entry}   $.ipv4AsmRanges
    ${exp_ipv4_asm_ranges}=   Create List{% for range in rp.ipv4_asm_ranges %}   {{ range }}{% endfor %}

    Lists Should Be Equal   ${rec_ipv4_asm_ranges}[0]   ${exp_ipv4_asm_ranges}   ignore_order=True   msg=IPv4 ASM ranges mismatch for RP {{ rp.name }}
    {% endif %}
    
    # Validate IPv6 ASM ranges
    {% if rp.ipv6_asm_ranges is defined and rp.ipv6_asm_ranges | length > 0 %}
    ${rec_ipv6_asm_ranges}=   Get Value From Json   ${rp_entry}   $.ipv6AsmRanges
    ${exp_ipv6_asm_ranges}=   Create List{% for range in rp.ipv6_asm_ranges %}   {{ range }}{% endfor %}

    Lists Should Be Equal   ${rec_ipv6_asm_ranges}[0]   ${exp_ipv6_asm_ranges}   ignore_order=True   msg=IPv6 ASM ranges mismatch for RP {{ rp.name }}
    {% endif %}
    
    {% endfor %}
    {% endif %}

{% endfor %}
{% endif %}
{% endfor %}

