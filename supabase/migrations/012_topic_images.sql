-- 012: a picture or a fact for every topic card (2026-10-30, the media session).
--
-- Paste into the Supabase SQL editor and run it once, after 010 and 011; it is safe to run
-- again. supabase/schema.sql gets the same text from the latency session.
--
-- A separate table rather than columns on `topics`, for four reasons:
--   * topics has a column-level grant for the browser roles (migration 003); this table has its
--     own, so that grant is not touched;
--   * one row can hold either an image with its credit or a fact card, never half of each (the
--     check constraints below);
--   * `locked` and `notes` are the Curator's, and stay out of the browser's grant, so a picture
--     or fact chosen by hand survives a re-run of `python -m curator.images`;
--   * it can be dropped to take the feature out, without touching the bank.
--
-- Pictures: only public domain, CC0, CC BY and CC BY-SA are accepted, decided in code
-- (curator/images.py). Each row keeps the author, the licence and the file page, because the
-- licences require the credit to be shown. The WebP files live in the public bucket
-- `topic-images` and are served from this site's own address (/media/*), so a visitor's browser
-- never contacts Wikimedia, NASA or Supabase for them.

create table if not exists public.topic_images (
    topic_id bigint primary key references public.topics (id) on delete cascade,
    kind text not null check (kind in ('image', 'fact')),
    -- kind = 'image'. Paths are inside the bucket, with a content hash in the name, so a file
    -- never changes under its name and can be cached for a year.
    card_path text,
    card_width integer,
    card_height integer,
    -- The 1200 x 630 link preview; null when the source picture is too small for it.
    preview_path text,
    source text check (source in ('wikipedia', 'nasa')),
    author text,
    licence_name text,
    licence_url text,
    file_page_url text,
    credit text,
    -- kind = 'fact': a category for the card's art, and one sentence from the topic's published
    -- explanation.
    category text,
    fact text,
    -- Set by hand to stop the fill from replacing this row.
    locked boolean not null default false,
    -- Why pictures were turned down, for whoever reads the dry run.
    notes text not null default '',
    updated_at timestamptz not null default now(),
    constraint topic_images_image_complete check (
        kind <> 'image' or (
            card_path is not null and card_width > 0 and card_height > 0
            and source is not null and author is not null and licence_name is not null
            and file_page_url is not null and credit is not null
        )
    ),
    constraint topic_images_fact_complete check (
        kind <> 'fact' or (category is not null and fact is not null)
    )
);

alter table public.topic_images enable row level security;

-- Readable exactly when the topic is: the same rule as the topics policy in schema.sql.
drop policy if exists "Images of readable topics are readable" on public.topic_images;
create policy "Images of readable topics are readable" on public.topic_images
    for select to anon, authenticated
    using (exists (
        select 1 from public.items i
        where i.topic_id = topic_images.topic_id
          and i.status = 'published' and i.report_count < 2
    ));

-- The browser roles read named columns only: `locked` and `notes` stay with the Curator.
revoke all on public.topic_images from anon, authenticated;
grant select (
    topic_id, kind, card_path, card_width, card_height, preview_path, source, author,
    licence_name, licence_url, file_page_url, credit, category, fact
) on public.topic_images to anon, authenticated;
grant all on public.topic_images to service_role;

-- The bucket. Public, so a file is served at /storage/v1/object/public/topic-images/<path>
-- (seo's /media/* rewrite points there). WebP only, 512 KB at most. Only the secret key
-- writes: no policy on storage.objects lets a browser role upload, change or list anything.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('topic-images', 'topic-images', true, 524288, array['image/webp'])
on conflict (id) do update
    set public = excluded.public,
        file_size_limit = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;
