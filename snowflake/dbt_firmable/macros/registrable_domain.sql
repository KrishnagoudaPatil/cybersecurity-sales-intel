{#-
  public_suffix_two_level(): a curated set of common TWO-LEVEL public suffixes
  (com.au, co.nz, co.uk, ne.jp, edu.tw, net.id, …). A lightweight stand-in for the
  full Public Suffix List; loading the real PSL as a seed is the production upgrade
  (see docs/improvements.md). Returned as a SQL IN-list literal so both the domain
  normaliser and the validity filter share one source of truth.
-#}
{% macro public_suffix_two_level() -%}
('com.au','net.au','org.au','asn.au','id.au','edu.au','gov.au',
 'co.nz','net.nz','org.nz','govt.nz','ac.nz','geek.nz','school.nz',
 'co.uk','org.uk','me.uk','ac.uk','gov.uk','ltd.uk','plc.uk','net.uk','sch.uk',
 'com.br','net.br','org.br','gov.br',
 'com.cn','net.cn','org.cn','gov.cn','edu.cn',
 'com.sg','edu.sg','gov.sg','net.sg','org.sg',
 'com.hk','edu.hk','gov.hk','net.hk','org.hk',
 'com.my','net.my','org.my','gov.my','edu.my',
 'com.tw','edu.tw','gov.tw','net.tw','org.tw','idv.tw',
 'co.in','net.in','org.in','gov.in','ac.in','edu.in',
 'co.id','net.id','or.id','ac.id','web.id','sch.id','go.id','my.id','biz.id',
 'co.jp','ne.jp','or.jp','ac.jp','go.jp','ad.jp','ed.jp','gr.jp','lg.jp',
 'co.kr','ne.kr','or.kr','re.kr','go.kr',
 'co.za','org.za','net.za','gov.za',
 'co.th','in.th','ac.th','go.th',
 'com.ph','net.ph','org.ph',
 'com.vn','net.vn','org.vn','edu.vn','gov.vn',
 'com.tr','com.mx','com.ar','com.sa','com.ua','com.co','com.pe','com.ec')
{%- endmacro %}


{#-
  registrable_domain(col): reduce a hostname to its registrable domain (eTLD+1),
  e.g. portal-dev.matrix-solutions.com -> matrix-solutions.com,
       api.acme.com.au                 -> acme.com.au.
  If the last two labels form a known two-level public suffix we keep three labels,
  otherwise two. Lowercased; leading "*." and trailing "." are stripped. Returns
  NULL for empty/degenerate input.
-#}
{% macro registrable_domain(col) -%}
{%- set parts = "split(lower(regexp_replace(rtrim(" ~ col ~ ", '.'), '^[*][.]', '')), '.')" -%}
(
  case
    when {{ col }} is null or trim({{ col }}) = '' then null
    when array_size({{ parts }}) < 2 then null
    when array_size({{ parts }}) >= 3
         and array_to_string(array_slice({{ parts }}, array_size({{ parts }}) - 2, array_size({{ parts }})), '.') in {{ public_suffix_two_level() }}
      then array_to_string(array_slice({{ parts }}, array_size({{ parts }}) - 3, array_size({{ parts }})), '.')
    else array_to_string(array_slice({{ parts }}, array_size({{ parts }}) - 2, array_size({{ parts }})), '.')
  end
)
{%- endmacro %}
