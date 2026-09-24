-- Restaurant POS — reference schema + demo data (PostgreSQL)
-- Regenerate with: python scripts/add_sample_restaurant.py (after a fresh install)
-- Contains ONLY the documented demo/sample accounts from README.md — no real
-- restaurant data. Default passwords/PINs here are the public demo ones and
-- must be changed before any real use.

--
-- PostgreSQL database dump
--

\restrict 7DVqgNz59iVnfUA9wSuHAZgbMYCCYrQWvhfQarLGDwPZ9OArFbxRzlb2gShVjGw

-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: app_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_settings (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    key character varying NOT NULL,
    value text,
    description text
);


--
-- Name: app_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.app_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: app_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.app_settings_id_seq OWNED BY public.app_settings.id;


--
-- Name: audit_trail; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_trail (
    id integer NOT NULL,
    restaurant_id integer,
    user_id integer,
    action character varying NOT NULL,
    table_name character varying NOT NULL,
    record_id integer,
    old_value text,
    new_value text,
    ip_address character varying,
    reason text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: audit_trail_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_trail_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_trail_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_trail_id_seq OWNED BY public.audit_trail.id;


--
-- Name: bill_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bill_payments (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    bill_id integer NOT NULL,
    method character varying NOT NULL,
    amount double precision NOT NULL,
    tendered double precision,
    reference character varying,
    received_by integer,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: bill_payments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bill_payments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bill_payments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bill_payments_id_seq OWNED BY public.bill_payments.id;


--
-- Name: bills; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bills (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    order_id integer NOT NULL,
    bill_number character varying NOT NULL,
    subtotal double precision NOT NULL,
    discount_type character varying,
    discount_value double precision,
    discount_amount double precision,
    taxable_amount double precision NOT NULL,
    vat_amount double precision,
    service_charge double precision,
    grand_total double precision NOT NULL,
    payment_method character varying,
    payment_status character varying,
    cashier_id integer,
    customer_pan character varying,
    customer_name character varying,
    is_printed boolean,
    print_count integer,
    synced_to_cbms boolean,
    cbms_sync_at timestamp without time zone,
    fiscal_year character varying,
    fonepay_prn character varying,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: bills_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bills_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bills_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bills_id_seq OWNED BY public.bills.id;


--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    name character varying NOT NULL,
    display_order integer,
    is_active boolean,
    station character varying,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- Name: customers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customers (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    name character varying NOT NULL,
    phone character varying NOT NULL,
    email character varying,
    total_visits integer,
    total_spent double precision,
    loyalty_points integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: customers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.customers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: customers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.customers_id_seq OWNED BY public.customers.id;


--
-- Name: ingredients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingredients (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    name character varying NOT NULL,
    unit character varying NOT NULL,
    current_stock double precision,
    minimum_stock double precision,
    cost_per_unit double precision,
    supplier_name character varying,
    last_purchased_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: ingredients_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ingredients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ingredients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ingredients_id_seq OWNED BY public.ingredients.id;


--
-- Name: menu_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.menu_items (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    category_id integer NOT NULL,
    name character varying NOT NULL,
    name_np character varying,
    price double precision NOT NULL,
    variant_type character varying,
    description text,
    is_vat_applicable boolean,
    is_available boolean,
    image_path character varying,
    display_order integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: menu_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.menu_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: menu_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.menu_items_id_seq OWNED BY public.menu_items.id;


--
-- Name: order_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.order_items (
    id integer NOT NULL,
    order_id integer NOT NULL,
    menu_item_id integer NOT NULL,
    quantity integer NOT NULL,
    unit_price double precision NOT NULL,
    notes character varying,
    kot_status character varying,
    kot_number integer,
    kot_sent_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: order_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.order_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: order_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.order_items_id_seq OWNED BY public.order_items.id;


--
-- Name: orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orders (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    table_id integer,
    order_type character varying NOT NULL,
    status character varying,
    waiter_id integer,
    customer_name character varying,
    customer_phone character varying,
    delivery_address text,
    guests integer,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: orders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.orders_id_seq OWNED BY public.orders.id;


--
-- Name: recipe_ingredients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_ingredients (
    id integer NOT NULL,
    menu_item_id integer NOT NULL,
    ingredient_id integer NOT NULL,
    quantity_used double precision NOT NULL,
    unit character varying NOT NULL
);


--
-- Name: recipe_ingredients_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recipe_ingredients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recipe_ingredients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recipe_ingredients_id_seq OWNED BY public.recipe_ingredients.id;


--
-- Name: reservations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reservations (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    table_id integer,
    customer_name character varying NOT NULL,
    customer_phone character varying,
    party_size integer NOT NULL,
    reserved_for timestamp without time zone NOT NULL,
    duration_min integer,
    status character varying,
    notes text,
    order_id integer,
    created_by integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: reservations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reservations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reservations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reservations_id_seq OWNED BY public.reservations.id;


--
-- Name: restaurant_tables; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.restaurant_tables (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    table_number character varying NOT NULL,
    capacity integer NOT NULL,
    status character varying,
    floor character varying,
    pos_x integer,
    pos_y integer,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: restaurant_tables_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.restaurant_tables_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: restaurant_tables_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.restaurant_tables_id_seq OWNED BY public.restaurant_tables.id;


--
-- Name: restaurants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.restaurants (
    id integer NOT NULL,
    name character varying NOT NULL,
    slug character varying NOT NULL,
    phone character varying,
    address character varying,
    vat_number character varying,
    is_active boolean,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: restaurants_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.restaurants_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: restaurants_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.restaurants_id_seq OWNED BY public.restaurants.id;


--
-- Name: stock_purchases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stock_purchases (
    id integer NOT NULL,
    ingredient_id integer NOT NULL,
    quantity double precision NOT NULL,
    cost_per_unit double precision NOT NULL,
    total_cost double precision NOT NULL,
    supplier_name character varying,
    purchased_by integer,
    purchased_at timestamp without time zone DEFAULT now()
);


--
-- Name: stock_purchases_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stock_purchases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stock_purchases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stock_purchases_id_seq OWNED BY public.stock_purchases.id;


--
-- Name: sync_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sync_log (
    id integer NOT NULL,
    table_name character varying NOT NULL,
    record_id integer NOT NULL,
    action character varying NOT NULL,
    data_snapshot text,
    is_synced boolean,
    synced_at timestamp without time zone,
    retry_count integer,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: sync_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sync_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sync_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sync_log_id_seq OWNED BY public.sync_log.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    restaurant_id integer,
    username character varying NOT NULL,
    password_hash character varying NOT NULL,
    full_name character varying NOT NULL,
    role character varying NOT NULL,
    is_active boolean,
    pin character varying,
    last_login timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: app_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_settings ALTER COLUMN id SET DEFAULT nextval('public.app_settings_id_seq'::regclass);


--
-- Name: audit_trail id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_trail ALTER COLUMN id SET DEFAULT nextval('public.audit_trail_id_seq'::regclass);


--
-- Name: bill_payments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_payments ALTER COLUMN id SET DEFAULT nextval('public.bill_payments_id_seq'::regclass);


--
-- Name: bills id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills ALTER COLUMN id SET DEFAULT nextval('public.bills_id_seq'::regclass);


--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Name: customers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers ALTER COLUMN id SET DEFAULT nextval('public.customers_id_seq'::regclass);


--
-- Name: ingredients id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredients ALTER COLUMN id SET DEFAULT nextval('public.ingredients_id_seq'::regclass);


--
-- Name: menu_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.menu_items ALTER COLUMN id SET DEFAULT nextval('public.menu_items_id_seq'::regclass);


--
-- Name: order_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_items ALTER COLUMN id SET DEFAULT nextval('public.order_items_id_seq'::regclass);


--
-- Name: orders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders ALTER COLUMN id SET DEFAULT nextval('public.orders_id_seq'::regclass);


--
-- Name: recipe_ingredients id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_ingredients ALTER COLUMN id SET DEFAULT nextval('public.recipe_ingredients_id_seq'::regclass);


--
-- Name: reservations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservations ALTER COLUMN id SET DEFAULT nextval('public.reservations_id_seq'::regclass);


--
-- Name: restaurant_tables id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.restaurant_tables ALTER COLUMN id SET DEFAULT nextval('public.restaurant_tables_id_seq'::regclass);


--
-- Name: restaurants id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.restaurants ALTER COLUMN id SET DEFAULT nextval('public.restaurants_id_seq'::regclass);


--
-- Name: stock_purchases id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_purchases ALTER COLUMN id SET DEFAULT nextval('public.stock_purchases_id_seq'::regclass);


--
-- Name: sync_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_log ALTER COLUMN id SET DEFAULT nextval('public.sync_log_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: app_settings; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.app_settings (id, restaurant_id, key, value, description) FROM stdin;
\.


--
-- Data for Name: audit_trail; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_trail (id, restaurant_id, user_id, action, table_name, record_id, old_value, new_value, ip_address, reason, created_at) FROM stdin;
\.


--
-- Data for Name: bill_payments; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.bill_payments (id, restaurant_id, bill_id, method, amount, tendered, reference, received_by, created_at) FROM stdin;
\.


--
-- Data for Name: bills; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.bills (id, restaurant_id, order_id, bill_number, subtotal, discount_type, discount_value, discount_amount, taxable_amount, vat_amount, service_charge, grand_total, payment_method, payment_status, cashier_id, customer_pan, customer_name, is_printed, print_count, synced_to_cbms, cbms_sync_at, fiscal_year, fonepay_prn, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: categories; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.categories (id, restaurant_id, name, display_order, is_active, station, created_at) FROM stdin;
1	1	Momo & Dumplings	1	t	kitchen	2026-09-24 18:47:23.252253
2	1	Dal Bhat Set	2	t	kitchen	2026-09-24 18:47:23.260504
3	1	Noodles & Rice	3	t	kitchen	2026-09-24 18:47:23.26457
4	1	Grill & Starters	4	t	kitchen	2026-09-24 18:47:23.266074
5	1	Hot Drinks	5	t	bar	2026-09-24 18:47:23.26796
6	1	Cold Drinks	6	t	none	2026-09-24 18:47:23.269847
7	1	Desserts	7	t	kitchen	2026-09-24 18:47:23.27148
8	2	Momo & Dumplings	1	t	kitchen	2026-09-24 18:47:25.055983
9	2	Dal Bhat Set	2	t	kitchen	2026-09-24 18:47:25.065463
10	2	Noodles & Rice	3	t	kitchen	2026-09-24 18:47:25.070245
11	2	Grill & Starters	4	t	kitchen	2026-09-24 18:47:25.072769
12	2	Hot Drinks	5	t	bar	2026-09-24 18:47:25.074718
13	2	Cold Drinks	6	t	none	2026-09-24 18:47:25.076022
14	2	Desserts	7	t	kitchen	2026-09-24 18:47:25.077192
\.


--
-- Data for Name: customers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.customers (id, restaurant_id, name, phone, email, total_visits, total_spent, loyalty_points, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: ingredients; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ingredients (id, restaurant_id, name, unit, current_stock, minimum_stock, cost_per_unit, supplier_name, last_purchased_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: menu_items; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.menu_items (id, restaurant_id, category_id, name, name_np, price, variant_type, description, is_vat_applicable, is_available, image_path, display_order, created_at, updated_at) FROM stdin;
1	1	1	Chicken Momo	चिकेन मम	250	\N	\N	t	t	\N	1	2026-09-24 18:47:23.262742	2026-09-24 18:47:23.262747
2	1	1	Veg Momo	भेज मम	180	\N	\N	t	t	\N	2	2026-09-24 18:47:23.262749	2026-09-24 18:47:23.26275
3	1	1	Buff Momo	बफ मम	220	\N	\N	t	t	\N	3	2026-09-24 18:47:23.262751	2026-09-24 18:47:23.262752
4	1	1	Jhol Momo	झोल मम	280	\N	\N	t	t	\N	4	2026-09-24 18:47:23.262753	2026-09-24 18:47:23.262754
5	1	1	C-Momo	सी-मम	300	\N	\N	t	t	\N	5	2026-09-24 18:47:23.262755	2026-09-24 18:47:23.262756
6	1	2	Dal Bhat Set Veg	दाल भात (भेज)	350	\N	\N	t	t	\N	1	2026-09-24 18:47:23.265198	2026-09-24 18:47:23.2652
7	1	2	Dal Bhat Set Chicken	दाल भात (चिकेन)	450	\N	\N	t	t	\N	2	2026-09-24 18:47:23.265201	2026-09-24 18:47:23.265202
8	1	2	Dal Bhat Set Mutton	दाल भात (खसी)	550	\N	\N	t	t	\N	3	2026-09-24 18:47:23.265202	2026-09-24 18:47:23.265203
9	1	3	Chicken Chowmein	चिकेन चाउमिन	200	\N	\N	t	t	\N	1	2026-09-24 18:47:23.26659	2026-09-24 18:47:23.266592
10	1	3	Veg Chowmein	भेज चाउमिन	160	\N	\N	t	t	\N	2	2026-09-24 18:47:23.266592	2026-09-24 18:47:23.266593
11	1	3	Fried Rice Chicken	चिकेन फ्राइड राइस	280	\N	\N	t	t	\N	3	2026-09-24 18:47:23.266593	2026-09-24 18:47:23.266594
12	1	3	Fried Rice Veg	भेज फ्राइड राइस	220	\N	\N	t	t	\N	4	2026-09-24 18:47:23.266594	2026-09-24 18:47:23.266595
13	1	3	Thukpa	थुक्पा	240	\N	\N	t	t	\N	5	2026-09-24 18:47:23.266595	2026-09-24 18:47:23.266596
14	1	4	Chicken Sekuwa	चिकेन सेकुवा	400	\N	\N	t	t	\N	1	2026-09-24 18:47:23.268574	2026-09-24 18:47:23.268578
15	1	4	Paneer Tikka	पनिर टिक्का	350	\N	\N	t	t	\N	2	2026-09-24 18:47:23.26858	2026-09-24 18:47:23.268581
16	1	4	Chicken Choila	चिकेन छोयला	380	\N	\N	t	t	\N	3	2026-09-24 18:47:23.268582	2026-09-24 18:47:23.268583
17	1	4	French Fries	फ्रेन्च फ्राइज	180	\N	\N	t	t	\N	4	2026-09-24 18:47:23.268584	2026-09-24 18:47:23.268585
18	1	5	Milk Tea	दुध चिया	40	\N	\N	t	t	\N	1	2026-09-24 18:47:23.270383	2026-09-24 18:47:23.270387
19	1	5	Lemon Tea	लेमन टी	60	\N	\N	t	t	\N	2	2026-09-24 18:47:23.270388	2026-09-24 18:47:23.270389
20	1	5	Black Coffee	कालो कफी	120	\N	\N	t	t	\N	3	2026-09-24 18:47:23.27039	2026-09-24 18:47:23.270391
21	1	5	Cappuccino	क्यापुचिनो	180	\N	\N	t	t	\N	4	2026-09-24 18:47:23.270391	2026-09-24 18:47:23.270392
22	1	6	Coke	कोक	80	\N	\N	t	t	\N	1	2026-09-24 18:47:23.271924	2026-09-24 18:47:23.271926
23	1	6	Fanta	फान्टा	80	\N	\N	t	t	\N	2	2026-09-24 18:47:23.271928	2026-09-24 18:47:23.271928
24	1	6	Mineral Water	पानी	40	\N	\N	t	t	\N	3	2026-09-24 18:47:23.271929	2026-09-24 18:47:23.27193
25	1	7	Kheer	खिर	120	\N	\N	t	t	\N	1	2026-09-24 18:47:23.273003	2026-09-24 18:47:23.273005
26	1	7	Gulab Jamun	गुलाब जामुन	150	\N	\N	t	t	\N	2	2026-09-24 18:47:23.273007	2026-09-24 18:47:23.273008
27	2	8	Chicken Momo	चिकेन मम	250	\N	\N	t	t	\N	1	2026-09-24 18:47:25.068006	2026-09-24 18:47:25.068011
28	2	8	Veg Momo	भेज मम	180	\N	\N	t	t	\N	2	2026-09-24 18:47:25.068013	2026-09-24 18:47:25.068014
29	2	8	Buff Momo	बफ मम	220	\N	\N	t	t	\N	3	2026-09-24 18:47:25.068015	2026-09-24 18:47:25.068016
30	2	8	Jhol Momo	झोल मम	280	\N	\N	t	t	\N	4	2026-09-24 18:47:25.068017	2026-09-24 18:47:25.068018
31	2	8	C-Momo	सी-मम	300	\N	\N	t	t	\N	5	2026-09-24 18:47:25.068019	2026-09-24 18:47:25.068019
32	2	9	Dal Bhat Set Veg	दाल भात (भेज)	350	\N	\N	t	t	\N	1	2026-09-24 18:47:25.071107	2026-09-24 18:47:25.071111
33	2	9	Dal Bhat Set Chicken	दाल भात (चिकेन)	450	\N	\N	t	t	\N	2	2026-09-24 18:47:25.071113	2026-09-24 18:47:25.071114
34	2	9	Dal Bhat Set Mutton	दाल भात (खसी)	550	\N	\N	t	t	\N	3	2026-09-24 18:47:25.071115	2026-09-24 18:47:25.071116
35	2	10	Chicken Chowmein	चिकेन चाउमिन	200	\N	\N	t	t	\N	1	2026-09-24 18:47:25.073595	2026-09-24 18:47:25.073599
36	2	10	Veg Chowmein	भेज चाउमिन	160	\N	\N	t	t	\N	2	2026-09-24 18:47:25.073601	2026-09-24 18:47:25.073602
37	2	10	Fried Rice Chicken	चिकेन फ्राइड राइस	280	\N	\N	t	t	\N	3	2026-09-24 18:47:25.073603	2026-09-24 18:47:25.073604
38	2	10	Fried Rice Veg	भेज फ्राइड राइस	220	\N	\N	t	t	\N	4	2026-09-24 18:47:25.073605	2026-09-24 18:47:25.073606
39	2	10	Thukpa	थुक्पा	240	\N	\N	t	t	\N	5	2026-09-24 18:47:25.073607	2026-09-24 18:47:25.073607
40	2	11	Chicken Sekuwa	चिकेन सेकुवा	400	\N	\N	t	t	\N	1	2026-09-24 18:47:25.075214	2026-09-24 18:47:25.075216
41	2	11	Paneer Tikka	पनिर टिक्का	350	\N	\N	t	t	\N	2	2026-09-24 18:47:25.075217	2026-09-24 18:47:25.075217
42	2	11	Chicken Choila	चिकेन छोयला	380	\N	\N	t	t	\N	3	2026-09-24 18:47:25.075218	2026-09-24 18:47:25.075218
43	2	11	French Fries	फ्रेन्च फ्राइज	180	\N	\N	t	t	\N	4	2026-09-24 18:47:25.075219	2026-09-24 18:47:25.075219
44	2	12	Milk Tea	दुध चिया	40	\N	\N	t	t	\N	1	2026-09-24 18:47:25.076405	2026-09-24 18:47:25.076407
45	2	12	Lemon Tea	लेमन टी	60	\N	\N	t	t	\N	2	2026-09-24 18:47:25.076408	2026-09-24 18:47:25.076408
46	2	12	Black Coffee	कालो कफी	120	\N	\N	t	t	\N	3	2026-09-24 18:47:25.076409	2026-09-24 18:47:25.076409
47	2	12	Cappuccino	क्यापुचिनो	180	\N	\N	t	t	\N	4	2026-09-24 18:47:25.07641	2026-09-24 18:47:25.07641
48	2	13	Coke	कोक	80	\N	\N	t	t	\N	1	2026-09-24 18:47:25.077532	2026-09-24 18:47:25.077534
49	2	13	Fanta	फान्टा	80	\N	\N	t	t	\N	2	2026-09-24 18:47:25.077535	2026-09-24 18:47:25.077535
50	2	13	Mineral Water	पानी	40	\N	\N	t	t	\N	3	2026-09-24 18:47:25.077536	2026-09-24 18:47:25.077536
51	2	14	Kheer	खिर	120	\N	\N	t	t	\N	1	2026-09-24 18:47:25.078568	2026-09-24 18:47:25.07857
52	2	14	Gulab Jamun	गुलाब जामुन	150	\N	\N	t	t	\N	2	2026-09-24 18:47:25.07857	2026-09-24 18:47:25.078571
\.


--
-- Data for Name: order_items; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.order_items (id, order_id, menu_item_id, quantity, unit_price, notes, kot_status, kot_number, kot_sent_at, created_at) FROM stdin;
\.


--
-- Data for Name: orders; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.orders (id, restaurant_id, table_id, order_type, status, waiter_id, customer_name, customer_phone, delivery_address, guests, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: recipe_ingredients; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.recipe_ingredients (id, menu_item_id, ingredient_id, quantity_used, unit) FROM stdin;
\.


--
-- Data for Name: reservations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.reservations (id, restaurant_id, table_id, customer_name, customer_phone, party_size, reserved_for, duration_min, status, notes, order_id, created_by, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: restaurant_tables; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.restaurant_tables (id, restaurant_id, table_number, capacity, status, floor, pos_x, pos_y, created_at) FROM stdin;
1	1	T1	2	free	Ground	0	0	2026-09-24 18:47:23.255068
2	1	T2	2	free	Ground	0	0	2026-09-24 18:47:23.255071
3	1	T3	4	free	Ground	0	0	2026-09-24 18:47:23.255072
4	1	T4	4	free	Ground	0	0	2026-09-24 18:47:23.255073
5	1	T5	4	free	Ground	0	0	2026-09-24 18:47:23.255073
6	1	T6	4	free	Ground	0	0	2026-09-24 18:47:23.255074
7	1	T7	4	free	Ground	0	0	2026-09-24 18:47:23.255074
8	1	T8	4	free	Ground	0	0	2026-09-24 18:47:23.255075
9	1	T9	6	free	First	0	0	2026-09-24 18:47:23.255076
10	1	T10	6	free	First	0	0	2026-09-24 18:47:23.255076
11	1	T11	6	free	First	0	0	2026-09-24 18:47:23.255077
12	1	T12	6	free	First	0	0	2026-09-24 18:47:23.255077
13	1	VIP-1	8	free	Rooftop	0	0	2026-09-24 18:47:23.255078
14	1	VIP-2	8	free	Rooftop	0	0	2026-09-24 18:47:23.255078
15	2	T1	2	free	Ground	0	0	2026-09-24 18:47:25.059198
16	2	T2	2	free	Ground	0	0	2026-09-24 18:47:25.059204
17	2	T3	4	free	Ground	0	0	2026-09-24 18:47:25.059207
18	2	T4	4	free	Ground	0	0	2026-09-24 18:47:25.059209
19	2	T5	4	free	Ground	0	0	2026-09-24 18:47:25.059211
20	2	T6	4	free	Ground	0	0	2026-09-24 18:47:25.059212
21	2	T7	4	free	Ground	0	0	2026-09-24 18:47:25.059214
22	2	T8	4	free	Ground	0	0	2026-09-24 18:47:25.059215
23	2	T9	6	free	First	0	0	2026-09-24 18:47:25.059216
24	2	T10	6	free	First	0	0	2026-09-24 18:47:25.059218
25	2	T11	6	free	First	0	0	2026-09-24 18:47:25.05922
26	2	T12	6	free	First	0	0	2026-09-24 18:47:25.059221
27	2	VIP-1	8	free	Rooftop	0	0	2026-09-24 18:47:25.059223
28	2	VIP-2	8	free	Rooftop	0	0	2026-09-24 18:47:25.059224
\.


--
-- Data for Name: restaurants; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.restaurants (id, name, slug, phone, address, vat_number, is_active, created_at) FROM stdin;
1	Demo Restaurant	demo	\N	\N	\N	t	2026-09-24 18:47:22.398262
2	Sample Restaurant	sample	01-4400000	Thamel, Kathmandu	\N	t	2026-09-24 18:47:24.213193
\.


--
-- Data for Name: stock_purchases; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.stock_purchases (id, ingredient_id, quantity, cost_per_unit, total_cost, supplier_name, purchased_by, purchased_at) FROM stdin;
\.


--
-- Data for Name: sync_log; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sync_log (id, table_name, record_id, action, data_snapshot, is_synced, synced_at, retry_count, created_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, restaurant_id, username, password_hash, full_name, role, is_active, pin, last_login, created_at, updated_at) FROM stdin;
1	\N	superadmin	$2b$12$cojxE1KRmLESj4wxHl2fMekCBSvVYoczTrs/Hu7xYMgMPXUWQQxvu	Platform Administrator	superadmin	t	\N	\N	2026-09-24 18:47:22.389866	2026-09-24 18:47:22.389874
2	1	admin	$2b$12$L4b6r0yO0mHuDLF/LHlQxuN6DbAM2qlwfLJkWlv88GUTyC5WqFy/2	Administrator	admin	t	0000	\N	2026-09-24 18:47:23.258185	2026-09-24 18:47:23.258191
3	1	cashier1	$2b$12$uuWF9/pOa1BqwfmQxKu6EeugW9kU5QmNOXe9XhBXSwu.XGuPFN.YC	Sita Cashier	cashier	t	1111	\N	2026-09-24 18:47:23.258192	2026-09-24 18:47:23.258193
4	1	waiter1	$2b$12$tMj/PFbCTMlEu5yuVv4cz.j16Ivp4nqW0h3L4WOCXiDEJe0I4KERS	Ram Waiter	waiter	t	2222	\N	2026-09-24 18:47:23.258194	2026-09-24 18:47:23.258195
5	1	kitchen1	$2b$12$Yx/kMdXhZQ1/YEB/rhHJRuFof1jNWezKdNVdSkSm6QpP0yHQabLDi	Hari Kitchen	kitchen	t	3333	\N	2026-09-24 18:47:23.258196	2026-09-24 18:47:23.258197
6	2	admin	$2b$12$Nw06dN3C5DzKdmk/oZUPReSyn9X9u4UCMJE58gAFg5Ei/LGxkpxj6	Sample Admin	admin	t	0000	\N	2026-09-24 18:47:25.063106	2026-09-24 18:47:25.063111
7	2	cashier1	$2b$12$csJS4O75woq.NfVY0p1rz.o6Nk/8rP.GHedPLL97WtjqUsWng2oie	Sita Cashier	cashier	t	1111	\N	2026-09-24 18:47:25.063112	2026-09-24 18:47:25.063113
8	2	waiter1	$2b$12$HqxJosLs5bIY..5x2lcD9uqym9ZmwsHofsy4Epf3vMU8.6gdRP3TC	Ram Waiter	waiter	t	2222	\N	2026-09-24 18:47:25.063114	2026-09-24 18:47:25.063115
9	2	kitchen1	$2b$12$sIUDeJ4QmKqXjk40lfrHiu1efVRZu1cv8GksVtYau5HcEMPkwEkhW	Hari Kitchen	kitchen	t	3333	\N	2026-09-24 18:47:25.063116	2026-09-24 18:47:25.063117
\.


--
-- Name: app_settings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.app_settings_id_seq', 1, false);


--
-- Name: audit_trail_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.audit_trail_id_seq', 1, false);


--
-- Name: bill_payments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.bill_payments_id_seq', 1, false);


--
-- Name: bills_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.bills_id_seq', 1, false);


--
-- Name: categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.categories_id_seq', 14, true);


--
-- Name: customers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.customers_id_seq', 1, false);


--
-- Name: ingredients_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ingredients_id_seq', 1, false);


--
-- Name: menu_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.menu_items_id_seq', 52, true);


--
-- Name: order_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.order_items_id_seq', 1, false);


--
-- Name: orders_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.orders_id_seq', 1, false);


--
-- Name: recipe_ingredients_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.recipe_ingredients_id_seq', 1, false);


--
-- Name: reservations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.reservations_id_seq', 1, false);


--
-- Name: restaurant_tables_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.restaurant_tables_id_seq', 28, true);


--
-- Name: restaurants_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.restaurants_id_seq', 2, true);


--
-- Name: stock_purchases_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.stock_purchases_id_seq', 1, false);


--
-- Name: sync_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.sync_log_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.users_id_seq', 9, true);


--
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (id);


--
-- Name: audit_trail audit_trail_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_trail
    ADD CONSTRAINT audit_trail_pkey PRIMARY KEY (id);


--
-- Name: bill_payments bill_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_payments
    ADD CONSTRAINT bill_payments_pkey PRIMARY KEY (id);


--
-- Name: bills bills_fonepay_prn_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_fonepay_prn_key UNIQUE (fonepay_prn);


--
-- Name: bills bills_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_pkey PRIMARY KEY (id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: ingredients ingredients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredients
    ADD CONSTRAINT ingredients_pkey PRIMARY KEY (id);


--
-- Name: menu_items menu_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.menu_items
    ADD CONSTRAINT menu_items_pkey PRIMARY KEY (id);


--
-- Name: order_items order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: recipe_ingredients recipe_ingredients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_ingredients
    ADD CONSTRAINT recipe_ingredients_pkey PRIMARY KEY (id);


--
-- Name: reservations reservations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservations
    ADD CONSTRAINT reservations_pkey PRIMARY KEY (id);


--
-- Name: restaurant_tables restaurant_tables_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.restaurant_tables
    ADD CONSTRAINT restaurant_tables_pkey PRIMARY KEY (id);


--
-- Name: restaurants restaurants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.restaurants
    ADD CONSTRAINT restaurants_pkey PRIMARY KEY (id);


--
-- Name: restaurants restaurants_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.restaurants
    ADD CONSTRAINT restaurants_slug_key UNIQUE (slug);


--
-- Name: stock_purchases stock_purchases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_purchases
    ADD CONSTRAINT stock_purchases_pkey PRIMARY KEY (id);


--
-- Name: sync_log sync_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_log
    ADD CONSTRAINT sync_log_pkey PRIMARY KEY (id);


--
-- Name: bills uq_bill_per_restaurant; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT uq_bill_per_restaurant UNIQUE (bill_number, restaurant_id);


--
-- Name: customers uq_customer_per_restaurant; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT uq_customer_per_restaurant UNIQUE (phone, restaurant_id);


--
-- Name: app_settings uq_setting_per_restaurant; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT uq_setting_per_restaurant UNIQUE (key, restaurant_id);


--
-- Name: restaurant_tables uq_table_per_restaurant; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.restaurant_tables
    ADD CONSTRAINT uq_table_per_restaurant UNIQUE (table_number, restaurant_id);


--
-- Name: users uq_user_per_restaurant; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_user_per_restaurant UNIQUE (username, restaurant_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_bill_payments_bill_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bill_payments_bill_id ON public.bill_payments USING btree (bill_id);


--
-- Name: ix_reservations_restaurant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reservations_restaurant_id ON public.reservations USING btree (restaurant_id);


--
-- Name: app_settings app_settings_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: audit_trail audit_trail_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_trail
    ADD CONSTRAINT audit_trail_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: audit_trail audit_trail_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_trail
    ADD CONSTRAINT audit_trail_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: bill_payments bill_payments_bill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_payments
    ADD CONSTRAINT bill_payments_bill_id_fkey FOREIGN KEY (bill_id) REFERENCES public.bills(id);


--
-- Name: bill_payments bill_payments_received_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_payments
    ADD CONSTRAINT bill_payments_received_by_fkey FOREIGN KEY (received_by) REFERENCES public.users(id);


--
-- Name: bill_payments bill_payments_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_payments
    ADD CONSTRAINT bill_payments_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: bills bills_cashier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_cashier_id_fkey FOREIGN KEY (cashier_id) REFERENCES public.users(id);


--
-- Name: bills bills_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: bills bills_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: categories categories_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: customers customers_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: ingredients ingredients_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredients
    ADD CONSTRAINT ingredients_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: menu_items menu_items_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.menu_items
    ADD CONSTRAINT menu_items_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: menu_items menu_items_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.menu_items
    ADD CONSTRAINT menu_items_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: order_items order_items_menu_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_menu_item_id_fkey FOREIGN KEY (menu_item_id) REFERENCES public.menu_items(id);


--
-- Name: order_items order_items_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: orders orders_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: orders orders_table_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_table_id_fkey FOREIGN KEY (table_id) REFERENCES public.restaurant_tables(id);


--
-- Name: orders orders_waiter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_waiter_id_fkey FOREIGN KEY (waiter_id) REFERENCES public.users(id);


--
-- Name: recipe_ingredients recipe_ingredients_ingredient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_ingredients
    ADD CONSTRAINT recipe_ingredients_ingredient_id_fkey FOREIGN KEY (ingredient_id) REFERENCES public.ingredients(id);


--
-- Name: recipe_ingredients recipe_ingredients_menu_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_ingredients
    ADD CONSTRAINT recipe_ingredients_menu_item_id_fkey FOREIGN KEY (menu_item_id) REFERENCES public.menu_items(id);


--
-- Name: reservations reservations_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservations
    ADD CONSTRAINT reservations_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: reservations reservations_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservations
    ADD CONSTRAINT reservations_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: reservations reservations_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservations
    ADD CONSTRAINT reservations_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: reservations reservations_table_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservations
    ADD CONSTRAINT reservations_table_id_fkey FOREIGN KEY (table_id) REFERENCES public.restaurant_tables(id);


--
-- Name: restaurant_tables restaurant_tables_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.restaurant_tables
    ADD CONSTRAINT restaurant_tables_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: stock_purchases stock_purchases_ingredient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_purchases
    ADD CONSTRAINT stock_purchases_ingredient_id_fkey FOREIGN KEY (ingredient_id) REFERENCES public.ingredients(id);


--
-- Name: stock_purchases stock_purchases_purchased_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_purchases
    ADD CONSTRAINT stock_purchases_purchased_by_fkey FOREIGN KEY (purchased_by) REFERENCES public.users(id);


--
-- Name: users users_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- PostgreSQL database dump complete
--

\unrestrict 7DVqgNz59iVnfUA9wSuHAZgbMYCCYrQWvhfQarLGDwPZ9OArFbxRzlb2gShVjGw

