--
-- PostgreSQL database dump
--

\restrict LtdNqxAE648MhKrwPFdkqNUMmR4vkUATpgCNUPRQ19XDgonJr3tQrCBsTehK5FK

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
-- Name: app_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.app_settings (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    key character varying NOT NULL,
    value character varying,
    description character varying
);


ALTER TABLE public.app_settings OWNER TO postgres;

--
-- Name: app_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.app_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.app_settings_id_seq OWNER TO postgres;

--
-- Name: app_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.app_settings_id_seq OWNED BY public.app_settings.id;


--
-- Name: audit_trail; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.audit_trail (
    id integer NOT NULL,
    restaurant_id integer,
    user_id integer,
    action character varying NOT NULL,
    table_name character varying NOT NULL,
    record_id integer,
    old_value character varying,
    new_value character varying,
    ip_address character varying,
    reason character varying,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.audit_trail OWNER TO postgres;

--
-- Name: audit_trail_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.audit_trail_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audit_trail_id_seq OWNER TO postgres;

--
-- Name: audit_trail_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.audit_trail_id_seq OWNED BY public.audit_trail.id;


--
-- Name: bills; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.bills OWNER TO postgres;

--
-- Name: bills_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bills_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bills_id_seq OWNER TO postgres;

--
-- Name: bills_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bills_id_seq OWNED BY public.bills.id;


--
-- Name: categories; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    name character varying NOT NULL,
    display_order integer,
    is_active boolean,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.categories OWNER TO postgres;

--
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.categories_id_seq OWNER TO postgres;

--
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- Name: customers; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.customers OWNER TO postgres;

--
-- Name: customers_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.customers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.customers_id_seq OWNER TO postgres;

--
-- Name: customers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.customers_id_seq OWNED BY public.customers.id;


--
-- Name: ingredients; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.ingredients OWNER TO postgres;

--
-- Name: ingredients_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ingredients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ingredients_id_seq OWNER TO postgres;

--
-- Name: ingredients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ingredients_id_seq OWNED BY public.ingredients.id;


--
-- Name: menu_items; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.menu_items (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    category_id integer NOT NULL,
    name character varying NOT NULL,
    name_np character varying,
    price double precision NOT NULL,
    variant_type character varying,
    description character varying,
    is_vat_applicable boolean,
    is_available boolean,
    image_path character varying,
    display_order integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.menu_items OWNER TO postgres;

--
-- Name: menu_items_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.menu_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.menu_items_id_seq OWNER TO postgres;

--
-- Name: menu_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.menu_items_id_seq OWNED BY public.menu_items.id;


--
-- Name: order_items; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.order_items OWNER TO postgres;

--
-- Name: order_items_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.order_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.order_items_id_seq OWNER TO postgres;

--
-- Name: order_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.order_items_id_seq OWNED BY public.order_items.id;


--
-- Name: orders; Type: TABLE; Schema: public; Owner: postgres
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
    notes character varying,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.orders OWNER TO postgres;

--
-- Name: orders_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.orders_id_seq OWNER TO postgres;

--
-- Name: orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.orders_id_seq OWNED BY public.orders.id;


--
-- Name: recipe_ingredients; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.recipe_ingredients (
    id integer NOT NULL,
    menu_item_id integer NOT NULL,
    ingredient_id integer NOT NULL,
    quantity_used double precision NOT NULL,
    unit character varying NOT NULL
);


ALTER TABLE public.recipe_ingredients OWNER TO postgres;

--
-- Name: recipe_ingredients_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.recipe_ingredients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.recipe_ingredients_id_seq OWNER TO postgres;

--
-- Name: recipe_ingredients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.recipe_ingredients_id_seq OWNED BY public.recipe_ingredients.id;


--
-- Name: restaurant_tables; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.restaurant_tables OWNER TO postgres;

--
-- Name: restaurant_tables_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.restaurant_tables_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.restaurant_tables_id_seq OWNER TO postgres;

--
-- Name: restaurant_tables_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.restaurant_tables_id_seq OWNED BY public.restaurant_tables.id;


--
-- Name: restaurants; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.restaurants OWNER TO postgres;

--
-- Name: restaurants_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.restaurants_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.restaurants_id_seq OWNER TO postgres;

--
-- Name: restaurants_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.restaurants_id_seq OWNED BY public.restaurants.id;


--
-- Name: stock_purchases; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.stock_purchases OWNER TO postgres;

--
-- Name: stock_purchases_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.stock_purchases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stock_purchases_id_seq OWNER TO postgres;

--
-- Name: stock_purchases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.stock_purchases_id_seq OWNED BY public.stock_purchases.id;


--
-- Name: sync_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sync_log (
    id integer NOT NULL,
    table_name character varying NOT NULL,
    record_id integer NOT NULL,
    action character varying NOT NULL,
    data_snapshot character varying,
    is_synced boolean,
    synced_at timestamp without time zone,
    retry_count integer,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.sync_log OWNER TO postgres;

--
-- Name: sync_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sync_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sync_log_id_seq OWNER TO postgres;

--
-- Name: sync_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sync_log_id_seq OWNED BY public.sync_log.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: app_settings id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_settings ALTER COLUMN id SET DEFAULT nextval('public.app_settings_id_seq'::regclass);


--
-- Name: audit_trail id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_trail ALTER COLUMN id SET DEFAULT nextval('public.audit_trail_id_seq'::regclass);


--
-- Name: bills id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bills ALTER COLUMN id SET DEFAULT nextval('public.bills_id_seq'::regclass);


--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Name: customers id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customers ALTER COLUMN id SET DEFAULT nextval('public.customers_id_seq'::regclass);


--
-- Name: ingredients id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ingredients ALTER COLUMN id SET DEFAULT nextval('public.ingredients_id_seq'::regclass);


--
-- Name: menu_items id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.menu_items ALTER COLUMN id SET DEFAULT nextval('public.menu_items_id_seq'::regclass);


--
-- Name: order_items id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_items ALTER COLUMN id SET DEFAULT nextval('public.order_items_id_seq'::regclass);


--
-- Name: orders id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders ALTER COLUMN id SET DEFAULT nextval('public.orders_id_seq'::regclass);


--
-- Name: recipe_ingredients id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recipe_ingredients ALTER COLUMN id SET DEFAULT nextval('public.recipe_ingredients_id_seq'::regclass);


--
-- Name: restaurant_tables id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.restaurant_tables ALTER COLUMN id SET DEFAULT nextval('public.restaurant_tables_id_seq'::regclass);


--
-- Name: restaurants id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.restaurants ALTER COLUMN id SET DEFAULT nextval('public.restaurants_id_seq'::regclass);


--
-- Name: stock_purchases id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stock_purchases ALTER COLUMN id SET DEFAULT nextval('public.stock_purchases_id_seq'::regclass);


--
-- Name: sync_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sync_log ALTER COLUMN id SET DEFAULT nextval('public.sync_log_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: app_settings; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.app_settings (id, restaurant_id, key, value, description) FROM stdin;
\.


--
-- Data for Name: audit_trail; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.audit_trail (id, restaurant_id, user_id, action, table_name, record_id, old_value, new_value, ip_address, reason, created_at) FROM stdin;
\.


--
-- Data for Name: bills; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.bills (id, restaurant_id, order_id, bill_number, subtotal, discount_type, discount_value, discount_amount, taxable_amount, vat_amount, service_charge, grand_total, payment_method, payment_status, cashier_id, customer_pan, customer_name, is_printed, print_count, synced_to_cbms, cbms_sync_at, fiscal_year, fonepay_prn, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: categories; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.categories (id, restaurant_id, name, display_order, is_active, created_at) FROM stdin;
1	1	Starters	1	t	2026-05-19 16:57:18
2	1	Test Cat Updated	99	t	2026-05-19 17:03:57
3	1	Test Cat Updated	99	t	2026-05-19 17:07:48
4	1	Test Cat Updated	99	t	2026-05-19 17:10:18
5	1	Test Cat Updated	99	t	2026-05-19 17:11:05
6	1	Test Cat Updated	99	t	2026-05-19 17:11:42
7	1	Test Cat Updated	99	t	2026-05-19 17:14:08
8	1	Test Cat Updated	99	t	2026-05-19 17:17:33
9	1	Test Cat Updated	99	t	2026-05-19 17:18:09
10	1	Test Cat Updated	99	t	2026-05-19 17:21:24
11	1	Test Cat Updated	99	t	2026-05-19 17:22:05
12	1	Test Cat Updated	99	t	2026-05-19 17:30:59
13	1	Test Cat Updated	99	t	2026-05-19 17:31:23
14	1	Test Cat Updated	99	t	2026-05-19 17:32:01
15	2	Snack	1	t	2026-05-19 18:25:55
16	1	Cutting Tea	0	t	2026-06-29 08:38:07
\.


--
-- Data for Name: customers; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.customers (id, restaurant_id, name, phone, email, total_visits, total_spent, loyalty_points, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: ingredients; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.ingredients (id, restaurant_id, name, unit, current_stock, minimum_stock, cost_per_unit, supplier_name, last_purchased_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: menu_items; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.menu_items (id, restaurant_id, category_id, name, name_np, price, variant_type, description, is_vat_applicable, is_available, image_path, display_order, created_at, updated_at) FROM stdin;
1	1	1	Chicken Momo	\N	250	\N	\N	t	f	\N	0	2026-05-19 16:57:18	2026-05-19 16:57:18
2	1	2	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:03:57	2026-05-19 17:03:57
3	1	3	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:07:48	2026-05-19 17:07:48
4	1	4	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:10:18	2026-05-19 17:10:18
5	1	5	Test Momo	\N	280	\N	\N	t	t	\N	0	2026-05-19 17:11:05	2026-05-19 17:36:25
6	1	6	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:11:42	2026-05-19 17:11:42
7	1	6	Order Test Item	\N	150	\N	\N	f	t	\N	0	2026-05-19 17:11:42	2026-05-19 17:11:42
8	1	7	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:14:08	2026-05-19 17:14:08
9	1	7	Order Test Item	\N	150	\N	\N	f	t	\N	0	2026-05-19 17:14:08	2026-05-19 17:14:08
10	1	8	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:17:33	2026-05-19 17:17:33
11	1	8	Order Test Item	\N	150	\N	\N	f	t	\N	0	2026-05-19 17:17:33	2026-05-19 17:17:33
12	1	9	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:18:09	2026-05-19 17:18:09
13	1	9	Order Test Item	\N	150	\N	\N	f	t	\N	0	2026-05-19 17:18:10	2026-05-19 17:18:10
14	1	10	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:21:24	2026-05-19 17:21:24
15	1	10	Order Test Item	\N	150	\N	\N	f	f	\N	0	2026-05-19 17:21:24	2026-05-20 03:55:52
16	1	11	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:22:05	2026-05-19 17:22:05
17	1	11	Order Test Item	\N	150	\N	\N	f	t	\N	0	2026-05-19 17:22:05	2026-05-19 17:22:05
18	1	12	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:30:59	2026-05-19 17:30:59
19	1	12	Order Test Item	\N	150	\N	\N	f	t	\N	0	2026-05-19 17:30:59	2026-05-19 17:30:59
20	1	13	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:31:23	2026-05-19 17:31:23
21	1	13	Order Test Item	\N	150	\N	\N	f	t	\N	0	2026-05-19 17:31:23	2026-05-19 17:31:23
22	1	14	Test Momo	\N	280	\N	\N	t	f	\N	0	2026-05-19 17:32:01	2026-05-19 17:32:01
23	1	14	Order Test Item	\N	150	\N	\N	f	f	\N	0	2026-05-19 17:32:01	2026-05-20 03:55:57
24	2	15	momo	momo	150	veg	\N	t	t	\N	1	2026-05-19 18:26:14	2026-05-19 18:26:14
\.


--
-- Data for Name: order_items; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.order_items (id, order_id, menu_item_id, quantity, unit_price, notes, kot_status, kot_number, kot_sent_at, created_at) FROM stdin;
1	1	5	4	280	\N	sent	1	2026-06-29 15:26:59.171147	2026-06-29 15:26:22.401418
\.


--
-- Data for Name: orders; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.orders (id, restaurant_id, table_id, order_type, status, waiter_id, customer_name, customer_phone, notes, created_at, updated_at) FROM stdin;
1	1	1	dine_in	cancelled	1	\N	\N	\N	2026-06-29 15:26:22.37973	2026-06-29 15:28:10.529868
2	1	2	dine_in	active	1	\N	\N	\N	2026-06-29 15:29:06.780127	2026-06-29 15:29:06.780127
\.


--
-- Data for Name: recipe_ingredients; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.recipe_ingredients (id, menu_item_id, ingredient_id, quantity_used, unit) FROM stdin;
\.


--
-- Data for Name: restaurant_tables; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.restaurant_tables (id, restaurant_id, table_number, capacity, status, floor, pos_x, pos_y, created_at) FROM stdin;
1	1	T1	4	free	Ground	0	0	2026-05-19 17:32:01
2	1	T2	4	occupied	Ground	0	0	2026-06-29 15:28:52.230909
\.


--
-- Data for Name: restaurants; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.restaurants (id, name, slug, phone, address, vat_number, is_active, created_at) FROM stdin;
1	Demo Restaurant	demo	\N	\N	\N	t	2026-05-19 18:22:58
2	Eve Grill and Chill	1011	9865321456	Buddhanagar	2501456	t	2026-05-19 18:24:06
\.


--
-- Data for Name: stock_purchases; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.stock_purchases (id, ingredient_id, quantity, cost_per_unit, total_cost, supplier_name, purchased_by, purchased_at) FROM stdin;
\.


--
-- Data for Name: sync_log; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.sync_log (id, table_name, record_id, action, data_snapshot, is_synced, synced_at, retry_count, created_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, restaurant_id, username, password_hash, full_name, role, is_active, pin, last_login, created_at, updated_at) FROM stdin;
3	2	jitpur	$2b$12$1vsLMpavnB8xmiQIQGqDLO1.TIvpW8hvQ0ITZRULf36PSo.uXvUqu	Jitpurey Sau	admin	t	\N	\N	2026-05-19 18:24:07	2026-05-19 18:24:07
1	1	admin	$2b$12$9Wy4k4sVtAFPmfVaHlUqiOVNI9/24y3aMA.0Z0auMC55Hl0rQG1cG	Administrator	admin	t	0000	2026-06-29 15:00:33.993686	2026-05-19 16:54:15	2026-06-29 15:00:33.636252
2	\N	superadmin	$2b$12$crMsPTYNU0X27D756grMa.SPz8bs6eEPwWwrmqba.YbDgar22aI6m	Platform Administrator	superadmin	t	\N	2026-06-29 15:16:09.730691	2026-05-19 18:22:58	2026-06-29 15:16:09.489145
\.


--
-- Name: app_settings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.app_settings_id_seq', 1, true);


--
-- Name: audit_trail_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.audit_trail_id_seq', 1, false);


--
-- Name: bills_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.bills_id_seq', 1, false);


--
-- Name: categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.categories_id_seq', 16, true);


--
-- Name: customers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.customers_id_seq', 1, true);


--
-- Name: ingredients_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.ingredients_id_seq', 1, true);


--
-- Name: menu_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.menu_items_id_seq', 24, true);


--
-- Name: order_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.order_items_id_seq', 1, true);


--
-- Name: orders_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.orders_id_seq', 2, true);


--
-- Name: recipe_ingredients_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.recipe_ingredients_id_seq', 1, true);


--
-- Name: restaurant_tables_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.restaurant_tables_id_seq', 2, true);


--
-- Name: restaurants_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.restaurants_id_seq', 2, true);


--
-- Name: stock_purchases_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.stock_purchases_id_seq', 1, true);


--
-- Name: sync_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sync_log_id_seq', 1, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 3, true);


--
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (id);


--
-- Name: audit_trail audit_trail_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_trail
    ADD CONSTRAINT audit_trail_pkey PRIMARY KEY (id);


--
-- Name: bills bills_fonepay_prn_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_fonepay_prn_key UNIQUE (fonepay_prn);


--
-- Name: bills bills_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_pkey PRIMARY KEY (id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: ingredients ingredients_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ingredients
    ADD CONSTRAINT ingredients_pkey PRIMARY KEY (id);


--
-- Name: menu_items menu_items_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.menu_items
    ADD CONSTRAINT menu_items_pkey PRIMARY KEY (id);


--
-- Name: order_items order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: recipe_ingredients recipe_ingredients_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recipe_ingredients
    ADD CONSTRAINT recipe_ingredients_pkey PRIMARY KEY (id);


--
-- Name: restaurant_tables restaurant_tables_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.restaurant_tables
    ADD CONSTRAINT restaurant_tables_pkey PRIMARY KEY (id);


--
-- Name: restaurants restaurants_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.restaurants
    ADD CONSTRAINT restaurants_pkey PRIMARY KEY (id);


--
-- Name: restaurants restaurants_slug_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.restaurants
    ADD CONSTRAINT restaurants_slug_key UNIQUE (slug);


--
-- Name: stock_purchases stock_purchases_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stock_purchases
    ADD CONSTRAINT stock_purchases_pkey PRIMARY KEY (id);


--
-- Name: sync_log sync_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sync_log
    ADD CONSTRAINT sync_log_pkey PRIMARY KEY (id);


--
-- Name: bills uq_bill_per_restaurant; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT uq_bill_per_restaurant UNIQUE (bill_number, restaurant_id);


--
-- Name: customers uq_customer_per_restaurant; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT uq_customer_per_restaurant UNIQUE (phone, restaurant_id);


--
-- Name: app_settings uq_setting_per_restaurant; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT uq_setting_per_restaurant UNIQUE (key, restaurant_id);


--
-- Name: restaurant_tables uq_table_per_restaurant; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.restaurant_tables
    ADD CONSTRAINT uq_table_per_restaurant UNIQUE (table_number, restaurant_id);


--
-- Name: users uq_user_per_restaurant; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_user_per_restaurant UNIQUE (username, restaurant_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: app_settings app_settings_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: audit_trail audit_trail_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_trail
    ADD CONSTRAINT audit_trail_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: audit_trail audit_trail_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_trail
    ADD CONSTRAINT audit_trail_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: bills bills_cashier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_cashier_id_fkey FOREIGN KEY (cashier_id) REFERENCES public.users(id);


--
-- Name: bills bills_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: bills bills_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: categories categories_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: customers customers_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: ingredients ingredients_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ingredients
    ADD CONSTRAINT ingredients_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: menu_items menu_items_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.menu_items
    ADD CONSTRAINT menu_items_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: menu_items menu_items_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.menu_items
    ADD CONSTRAINT menu_items_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: order_items order_items_menu_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_menu_item_id_fkey FOREIGN KEY (menu_item_id) REFERENCES public.menu_items(id);


--
-- Name: order_items order_items_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: orders orders_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: orders orders_table_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_table_id_fkey FOREIGN KEY (table_id) REFERENCES public.restaurant_tables(id);


--
-- Name: orders orders_waiter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_waiter_id_fkey FOREIGN KEY (waiter_id) REFERENCES public.users(id);


--
-- Name: recipe_ingredients recipe_ingredients_ingredient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recipe_ingredients
    ADD CONSTRAINT recipe_ingredients_ingredient_id_fkey FOREIGN KEY (ingredient_id) REFERENCES public.ingredients(id);


--
-- Name: recipe_ingredients recipe_ingredients_menu_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recipe_ingredients
    ADD CONSTRAINT recipe_ingredients_menu_item_id_fkey FOREIGN KEY (menu_item_id) REFERENCES public.menu_items(id);


--
-- Name: restaurant_tables restaurant_tables_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.restaurant_tables
    ADD CONSTRAINT restaurant_tables_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: stock_purchases stock_purchases_ingredient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stock_purchases
    ADD CONSTRAINT stock_purchases_ingredient_id_fkey FOREIGN KEY (ingredient_id) REFERENCES public.ingredients(id);


--
-- Name: stock_purchases stock_purchases_purchased_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stock_purchases
    ADD CONSTRAINT stock_purchases_purchased_by_fkey FOREIGN KEY (purchased_by) REFERENCES public.users(id);


--
-- Name: users users_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- PostgreSQL database dump complete
--

\unrestrict LtdNqxAE648MhKrwPFdkqNUMmR4vkUATpgCNUPRQ19XDgonJr3tQrCBsTehK5FK

