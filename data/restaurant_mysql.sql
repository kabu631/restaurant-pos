-- Restaurant POS — reference schema + demo data (MySQL/MariaDB — XAMPP)
-- Regenerate with: python scripts/add_sample_restaurant.py (after a fresh install)
-- Contains ONLY the documented demo/sample accounts from README.md — no real
-- restaurant data. Default passwords/PINs here are the public demo ones and
-- must be changed before any real use.

-- MariaDB dump 10.19  Distrib 10.4.32-MariaDB, for Win64 (AMD64)
--
-- Host: localhost    Database: pos_scratch_dump
-- ------------------------------------------------------
-- Server version	10.4.32-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `app_settings`
--

DROP TABLE IF EXISTS `app_settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `app_settings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `key` varchar(255) NOT NULL,
  `value` mediumtext DEFAULT NULL,
  `description` mediumtext DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_setting_per_restaurant` (`key`,`restaurant_id`),
  KEY `restaurant_id` (`restaurant_id`),
  CONSTRAINT `app_settings_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `app_settings`
--

LOCK TABLES `app_settings` WRITE;
/*!40000 ALTER TABLE `app_settings` DISABLE KEYS */;
/*!40000 ALTER TABLE `app_settings` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `audit_trail`
--

DROP TABLE IF EXISTS `audit_trail`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `audit_trail` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `action` varchar(255) NOT NULL,
  `table_name` varchar(255) NOT NULL,
  `record_id` int(11) DEFAULT NULL,
  `old_value` mediumtext DEFAULT NULL,
  `new_value` mediumtext DEFAULT NULL,
  `ip_address` varchar(255) DEFAULT NULL,
  `reason` mediumtext DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `restaurant_id` (`restaurant_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `audit_trail_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`),
  CONSTRAINT `audit_trail_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `audit_trail`
--

LOCK TABLES `audit_trail` WRITE;
/*!40000 ALTER TABLE `audit_trail` DISABLE KEYS */;
/*!40000 ALTER TABLE `audit_trail` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `bill_payments`
--

DROP TABLE IF EXISTS `bill_payments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `bill_payments` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `bill_id` int(11) NOT NULL,
  `method` varchar(255) NOT NULL,
  `amount` double NOT NULL,
  `tendered` double DEFAULT NULL,
  `reference` varchar(255) DEFAULT NULL,
  `received_by` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `restaurant_id` (`restaurant_id`),
  KEY `received_by` (`received_by`),
  KEY `ix_bill_payments_bill_id` (`bill_id`),
  CONSTRAINT `bill_payments_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`),
  CONSTRAINT `bill_payments_ibfk_2` FOREIGN KEY (`bill_id`) REFERENCES `bills` (`id`),
  CONSTRAINT `bill_payments_ibfk_3` FOREIGN KEY (`received_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bill_payments`
--

LOCK TABLES `bill_payments` WRITE;
/*!40000 ALTER TABLE `bill_payments` DISABLE KEYS */;
/*!40000 ALTER TABLE `bill_payments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `bills`
--

DROP TABLE IF EXISTS `bills`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `bills` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `order_id` int(11) NOT NULL,
  `bill_number` varchar(255) NOT NULL,
  `subtotal` double NOT NULL,
  `discount_type` varchar(255) DEFAULT NULL,
  `discount_value` double DEFAULT NULL,
  `discount_amount` double DEFAULT NULL,
  `taxable_amount` double NOT NULL,
  `vat_amount` double DEFAULT NULL,
  `service_charge` double DEFAULT NULL,
  `grand_total` double NOT NULL,
  `payment_method` varchar(255) DEFAULT NULL,
  `payment_status` varchar(255) DEFAULT NULL,
  `cashier_id` int(11) DEFAULT NULL,
  `customer_pan` varchar(255) DEFAULT NULL,
  `customer_name` varchar(255) DEFAULT NULL,
  `is_printed` tinyint(1) DEFAULT NULL,
  `print_count` int(11) DEFAULT NULL,
  `synced_to_cbms` tinyint(1) DEFAULT NULL,
  `cbms_sync_at` datetime DEFAULT NULL,
  `fiscal_year` varchar(255) DEFAULT NULL,
  `fonepay_prn` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_bill_per_restaurant` (`bill_number`,`restaurant_id`),
  UNIQUE KEY `fonepay_prn` (`fonepay_prn`),
  KEY `restaurant_id` (`restaurant_id`),
  KEY `order_id` (`order_id`),
  KEY `cashier_id` (`cashier_id`),
  CONSTRAINT `bills_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`),
  CONSTRAINT `bills_ibfk_2` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`),
  CONSTRAINT `bills_ibfk_3` FOREIGN KEY (`cashier_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bills`
--

LOCK TABLES `bills` WRITE;
/*!40000 ALTER TABLE `bills` DISABLE KEYS */;
/*!40000 ALTER TABLE `bills` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `cash_movements`
--

DROP TABLE IF EXISTS `cash_movements`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cash_movements` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `shift_id` int(11) NOT NULL,
  `kind` varchar(5) NOT NULL,
  `amount` double NOT NULL,
  `reason` varchar(200) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `restaurant_id` (`restaurant_id`),
  KEY `user_id` (`user_id`),
  KEY `ix_cash_movements_shift_id` (`shift_id`),
  CONSTRAINT `cash_movements_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`),
  CONSTRAINT `cash_movements_ibfk_2` FOREIGN KEY (`shift_id`) REFERENCES `cash_shifts` (`id`),
  CONSTRAINT `cash_movements_ibfk_3` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cash_movements`
--

LOCK TABLES `cash_movements` WRITE;
/*!40000 ALTER TABLE `cash_movements` DISABLE KEYS */;
/*!40000 ALTER TABLE `cash_movements` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `cash_shifts`
--

DROP TABLE IF EXISTS `cash_shifts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cash_shifts` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `status` varchar(10) NOT NULL,
  `opened_by` int(11) NOT NULL,
  `opened_at` datetime DEFAULT current_timestamp(),
  `opening_float` double NOT NULL,
  `closed_by` int(11) DEFAULT NULL,
  `closed_at` datetime DEFAULT NULL,
  `expected_cash` double DEFAULT NULL,
  `counted_cash` double DEFAULT NULL,
  `difference` double DEFAULT NULL,
  `notes` varchar(500) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `opened_by` (`opened_by`),
  KEY `closed_by` (`closed_by`),
  KEY `ix_cash_shifts_restaurant_id` (`restaurant_id`),
  CONSTRAINT `cash_shifts_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`),
  CONSTRAINT `cash_shifts_ibfk_2` FOREIGN KEY (`opened_by`) REFERENCES `users` (`id`),
  CONSTRAINT `cash_shifts_ibfk_3` FOREIGN KEY (`closed_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cash_shifts`
--

LOCK TABLES `cash_shifts` WRITE;
/*!40000 ALTER TABLE `cash_shifts` DISABLE KEYS */;
/*!40000 ALTER TABLE `cash_shifts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `categories`
--

DROP TABLE IF EXISTS `categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `categories` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `display_order` int(11) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT NULL,
  `station` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `restaurant_id` (`restaurant_id`),
  CONSTRAINT `categories_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `categories`
--

LOCK TABLES `categories` WRITE;
/*!40000 ALTER TABLE `categories` DISABLE KEYS */;
INSERT INTO `categories` VALUES (1,1,'Momo & Dumplings',1,1,'kitchen','2026-09-24 19:43:41'),(2,1,'Dal Bhat Set',2,1,'kitchen','2026-09-24 19:43:41'),(3,1,'Noodles & Rice',3,1,'kitchen','2026-09-24 19:43:41'),(4,1,'Grill & Starters',4,1,'kitchen','2026-09-24 19:43:41'),(5,1,'Hot Drinks',5,1,'bar','2026-09-24 19:43:41'),(6,1,'Cold Drinks',6,1,'none','2026-09-24 19:43:41'),(7,1,'Desserts',7,1,'kitchen','2026-09-24 19:43:41'),(8,2,'Momo & Dumplings',1,1,'kitchen','2026-09-24 19:43:43'),(9,2,'Dal Bhat Set',2,1,'kitchen','2026-09-24 19:43:43'),(10,2,'Noodles & Rice',3,1,'kitchen','2026-09-24 19:43:43'),(11,2,'Grill & Starters',4,1,'kitchen','2026-09-24 19:43:43'),(12,2,'Hot Drinks',5,1,'bar','2026-09-24 19:43:43'),(13,2,'Cold Drinks',6,1,'none','2026-09-24 19:43:43'),(14,2,'Desserts',7,1,'kitchen','2026-09-24 19:43:43');
/*!40000 ALTER TABLE `categories` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `customers`
--

DROP TABLE IF EXISTS `customers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `customers` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `phone` varchar(255) NOT NULL,
  `email` varchar(255) DEFAULT NULL,
  `total_visits` int(11) DEFAULT NULL,
  `total_spent` double DEFAULT NULL,
  `loyalty_points` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_customer_per_restaurant` (`phone`,`restaurant_id`),
  KEY `restaurant_id` (`restaurant_id`),
  CONSTRAINT `customers_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `customers`
--

LOCK TABLES `customers` WRITE;
/*!40000 ALTER TABLE `customers` DISABLE KEYS */;
/*!40000 ALTER TABLE `customers` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ingredients`
--

DROP TABLE IF EXISTS `ingredients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ingredients` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `unit` varchar(255) NOT NULL,
  `current_stock` double DEFAULT NULL,
  `minimum_stock` double DEFAULT NULL,
  `cost_per_unit` double DEFAULT NULL,
  `supplier_name` varchar(255) DEFAULT NULL,
  `last_purchased_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `restaurant_id` (`restaurant_id`),
  CONSTRAINT `ingredients_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ingredients`
--

LOCK TABLES `ingredients` WRITE;
/*!40000 ALTER TABLE `ingredients` DISABLE KEYS */;
/*!40000 ALTER TABLE `ingredients` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `menu_items`
--

DROP TABLE IF EXISTS `menu_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `menu_items` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `category_id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `name_np` varchar(255) DEFAULT NULL,
  `price` double NOT NULL,
  `variant_type` varchar(255) DEFAULT NULL,
  `description` mediumtext DEFAULT NULL,
  `is_vat_applicable` tinyint(1) DEFAULT NULL,
  `is_available` tinyint(1) DEFAULT NULL,
  `image_path` varchar(255) DEFAULT NULL,
  `display_order` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `restaurant_id` (`restaurant_id`),
  KEY `category_id` (`category_id`),
  CONSTRAINT `menu_items_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`),
  CONSTRAINT `menu_items_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=53 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `menu_items`
--

LOCK TABLES `menu_items` WRITE;
/*!40000 ALTER TABLE `menu_items` DISABLE KEYS */;
INSERT INTO `menu_items` VALUES (1,1,1,'Chicken Momo','चिकेन मम',250,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(2,1,1,'Veg Momo','भेज मम',180,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(3,1,1,'Buff Momo','बफ मम',220,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(4,1,1,'Jhol Momo','झोल मम',280,NULL,NULL,1,1,NULL,4,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(5,1,1,'C-Momo','सी-मम',300,NULL,NULL,1,1,NULL,5,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(6,1,2,'Dal Bhat Set Veg','दाल भात (भेज)',350,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(7,1,2,'Dal Bhat Set Chicken','दाल भात (चिकेन)',450,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(8,1,2,'Dal Bhat Set Mutton','दाल भात (खसी)',550,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(9,1,3,'Chicken Chowmein','चिकेन चाउमिन',200,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(10,1,3,'Veg Chowmein','भेज चाउमिन',160,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(11,1,3,'Fried Rice Chicken','चिकेन फ्राइड राइस',280,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(12,1,3,'Fried Rice Veg','भेज फ्राइड राइस',220,NULL,NULL,1,1,NULL,4,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(13,1,3,'Thukpa','थुक्पा',240,NULL,NULL,1,1,NULL,5,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(14,1,4,'Chicken Sekuwa','चिकेन सेकुवा',400,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(15,1,4,'Paneer Tikka','पनिर टिक्का',350,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(16,1,4,'Chicken Choila','चिकेन छोयला',380,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(17,1,4,'French Fries','फ्रेन्च फ्राइज',180,NULL,NULL,1,1,NULL,4,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(18,1,5,'Milk Tea','दुध चिया',40,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(19,1,5,'Lemon Tea','लेमन टी',60,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(20,1,5,'Black Coffee','कालो कफी',120,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(21,1,5,'Cappuccino','क्यापुचिनो',180,NULL,NULL,1,1,NULL,4,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(22,1,6,'Coke','कोक',80,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(23,1,6,'Fanta','फान्टा',80,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(24,1,6,'Mineral Water','पानी',40,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(25,1,7,'Kheer','खिर',120,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(26,1,7,'Gulab Jamun','गुलाब जामुन',150,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(27,2,8,'Chicken Momo','चिकेन मम',250,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(28,2,8,'Veg Momo','भेज मम',180,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(29,2,8,'Buff Momo','बफ मम',220,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(30,2,8,'Jhol Momo','झोल मम',280,NULL,NULL,1,1,NULL,4,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(31,2,8,'C-Momo','सी-मम',300,NULL,NULL,1,1,NULL,5,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(32,2,9,'Dal Bhat Set Veg','दाल भात (भेज)',350,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(33,2,9,'Dal Bhat Set Chicken','दाल भात (चिकेन)',450,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(34,2,9,'Dal Bhat Set Mutton','दाल भात (खसी)',550,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(35,2,10,'Chicken Chowmein','चिकेन चाउमिन',200,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(36,2,10,'Veg Chowmein','भेज चाउमिन',160,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(37,2,10,'Fried Rice Chicken','चिकेन फ्राइड राइस',280,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(38,2,10,'Fried Rice Veg','भेज फ्राइड राइस',220,NULL,NULL,1,1,NULL,4,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(39,2,10,'Thukpa','थुक्पा',240,NULL,NULL,1,1,NULL,5,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(40,2,11,'Chicken Sekuwa','चिकेन सेकुवा',400,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(41,2,11,'Paneer Tikka','पनिर टिक्का',350,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(42,2,11,'Chicken Choila','चिकेन छोयला',380,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(43,2,11,'French Fries','फ्रेन्च फ्राइज',180,NULL,NULL,1,1,NULL,4,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(44,2,12,'Milk Tea','दुध चिया',40,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(45,2,12,'Lemon Tea','लेमन टी',60,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(46,2,12,'Black Coffee','कालो कफी',120,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(47,2,12,'Cappuccino','क्यापुचिनो',180,NULL,NULL,1,1,NULL,4,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(48,2,13,'Coke','कोक',80,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(49,2,13,'Fanta','फान्टा',80,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(50,2,13,'Mineral Water','पानी',40,NULL,NULL,1,1,NULL,3,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(51,2,14,'Kheer','खिर',120,NULL,NULL,1,1,NULL,1,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(52,2,14,'Gulab Jamun','गुलाब जामुन',150,NULL,NULL,1,1,NULL,2,'2026-09-24 19:43:43','2026-09-24 19:43:43');
/*!40000 ALTER TABLE `menu_items` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `order_items`
--

DROP TABLE IF EXISTS `order_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `order_items` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `order_id` int(11) NOT NULL,
  `menu_item_id` int(11) NOT NULL,
  `quantity` int(11) NOT NULL,
  `unit_price` double NOT NULL,
  `notes` varchar(255) DEFAULT NULL,
  `kot_status` varchar(255) DEFAULT NULL,
  `kot_number` int(11) DEFAULT NULL,
  `kot_sent_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `order_id` (`order_id`),
  KEY `menu_item_id` (`menu_item_id`),
  CONSTRAINT `order_items_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`),
  CONSTRAINT `order_items_ibfk_2` FOREIGN KEY (`menu_item_id`) REFERENCES `menu_items` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `order_items`
--

LOCK TABLES `order_items` WRITE;
/*!40000 ALTER TABLE `order_items` DISABLE KEYS */;
/*!40000 ALTER TABLE `order_items` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `orders`
--

DROP TABLE IF EXISTS `orders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `orders` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `table_id` int(11) DEFAULT NULL,
  `order_type` varchar(255) NOT NULL,
  `status` varchar(255) DEFAULT NULL,
  `waiter_id` int(11) DEFAULT NULL,
  `customer_name` varchar(255) DEFAULT NULL,
  `customer_phone` varchar(255) DEFAULT NULL,
  `delivery_address` mediumtext DEFAULT NULL,
  `guests` int(11) DEFAULT NULL,
  `notes` mediumtext DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `restaurant_id` (`restaurant_id`),
  KEY `table_id` (`table_id`),
  KEY `waiter_id` (`waiter_id`),
  CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`),
  CONSTRAINT `orders_ibfk_2` FOREIGN KEY (`table_id`) REFERENCES `restaurant_tables` (`id`),
  CONSTRAINT `orders_ibfk_3` FOREIGN KEY (`waiter_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `orders`
--

LOCK TABLES `orders` WRITE;
/*!40000 ALTER TABLE `orders` DISABLE KEYS */;
/*!40000 ALTER TABLE `orders` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `recipe_ingredients`
--

DROP TABLE IF EXISTS `recipe_ingredients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `recipe_ingredients` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `menu_item_id` int(11) NOT NULL,
  `ingredient_id` int(11) NOT NULL,
  `quantity_used` double NOT NULL,
  `unit` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `menu_item_id` (`menu_item_id`),
  KEY `ingredient_id` (`ingredient_id`),
  CONSTRAINT `recipe_ingredients_ibfk_1` FOREIGN KEY (`menu_item_id`) REFERENCES `menu_items` (`id`),
  CONSTRAINT `recipe_ingredients_ibfk_2` FOREIGN KEY (`ingredient_id`) REFERENCES `ingredients` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `recipe_ingredients`
--

LOCK TABLES `recipe_ingredients` WRITE;
/*!40000 ALTER TABLE `recipe_ingredients` DISABLE KEYS */;
/*!40000 ALTER TABLE `recipe_ingredients` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `reservations`
--

DROP TABLE IF EXISTS `reservations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reservations` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `table_id` int(11) DEFAULT NULL,
  `customer_name` varchar(255) NOT NULL,
  `customer_phone` varchar(255) DEFAULT NULL,
  `party_size` int(11) NOT NULL,
  `reserved_for` datetime NOT NULL,
  `duration_min` int(11) DEFAULT NULL,
  `status` varchar(255) DEFAULT NULL,
  `notes` mediumtext DEFAULT NULL,
  `order_id` int(11) DEFAULT NULL,
  `created_by` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `table_id` (`table_id`),
  KEY `order_id` (`order_id`),
  KEY `created_by` (`created_by`),
  KEY `ix_reservations_restaurant_id` (`restaurant_id`),
  CONSTRAINT `reservations_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`),
  CONSTRAINT `reservations_ibfk_2` FOREIGN KEY (`table_id`) REFERENCES `restaurant_tables` (`id`),
  CONSTRAINT `reservations_ibfk_3` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`),
  CONSTRAINT `reservations_ibfk_4` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `reservations`
--

LOCK TABLES `reservations` WRITE;
/*!40000 ALTER TABLE `reservations` DISABLE KEYS */;
/*!40000 ALTER TABLE `reservations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `restaurant_tables`
--

DROP TABLE IF EXISTS `restaurant_tables`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `restaurant_tables` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) NOT NULL,
  `table_number` varchar(255) NOT NULL,
  `capacity` int(11) NOT NULL,
  `status` varchar(255) DEFAULT NULL,
  `floor` varchar(255) DEFAULT NULL,
  `pos_x` int(11) DEFAULT NULL,
  `pos_y` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_table_per_restaurant` (`table_number`,`restaurant_id`),
  KEY `restaurant_id` (`restaurant_id`),
  CONSTRAINT `restaurant_tables_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `restaurant_tables`
--

LOCK TABLES `restaurant_tables` WRITE;
/*!40000 ALTER TABLE `restaurant_tables` DISABLE KEYS */;
INSERT INTO `restaurant_tables` VALUES (1,1,'T1',2,'free','Ground',0,0,'2026-09-24 19:43:41'),(2,1,'T2',2,'free','Ground',0,0,'2026-09-24 19:43:41'),(3,1,'T3',4,'free','Ground',0,0,'2026-09-24 19:43:41'),(4,1,'T4',4,'free','Ground',0,0,'2026-09-24 19:43:41'),(5,1,'T5',4,'free','Ground',0,0,'2026-09-24 19:43:41'),(6,1,'T6',4,'free','Ground',0,0,'2026-09-24 19:43:41'),(7,1,'T7',4,'free','Ground',0,0,'2026-09-24 19:43:41'),(8,1,'T8',4,'free','Ground',0,0,'2026-09-24 19:43:41'),(9,1,'T9',6,'free','First',0,0,'2026-09-24 19:43:41'),(10,1,'T10',6,'free','First',0,0,'2026-09-24 19:43:41'),(11,1,'T11',6,'free','First',0,0,'2026-09-24 19:43:41'),(12,1,'T12',6,'free','First',0,0,'2026-09-24 19:43:41'),(13,1,'VIP-1',8,'free','Rooftop',0,0,'2026-09-24 19:43:41'),(14,1,'VIP-2',8,'free','Rooftop',0,0,'2026-09-24 19:43:41'),(15,2,'T1',2,'free','Ground',0,0,'2026-09-24 19:43:43'),(16,2,'T2',2,'free','Ground',0,0,'2026-09-24 19:43:43'),(17,2,'T3',4,'free','Ground',0,0,'2026-09-24 19:43:43'),(18,2,'T4',4,'free','Ground',0,0,'2026-09-24 19:43:43'),(19,2,'T5',4,'free','Ground',0,0,'2026-09-24 19:43:43'),(20,2,'T6',4,'free','Ground',0,0,'2026-09-24 19:43:43'),(21,2,'T7',4,'free','Ground',0,0,'2026-09-24 19:43:43'),(22,2,'T8',4,'free','Ground',0,0,'2026-09-24 19:43:43'),(23,2,'T9',6,'free','First',0,0,'2026-09-24 19:43:43'),(24,2,'T10',6,'free','First',0,0,'2026-09-24 19:43:43'),(25,2,'T11',6,'free','First',0,0,'2026-09-24 19:43:43'),(26,2,'T12',6,'free','First',0,0,'2026-09-24 19:43:43'),(27,2,'VIP-1',8,'free','Rooftop',0,0,'2026-09-24 19:43:43'),(28,2,'VIP-2',8,'free','Rooftop',0,0,'2026-09-24 19:43:43');
/*!40000 ALTER TABLE `restaurant_tables` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `restaurants`
--

DROP TABLE IF EXISTS `restaurants`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `restaurants` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `slug` varchar(255) NOT NULL,
  `phone` varchar(255) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `vat_number` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `slug` (`slug`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `restaurants`
--

LOCK TABLES `restaurants` WRITE;
/*!40000 ALTER TABLE `restaurants` DISABLE KEYS */;
INSERT INTO `restaurants` VALUES (1,'Demo Restaurant','demo',NULL,NULL,NULL,1,'2026-09-24 19:43:40'),(2,'Sample Restaurant','sample','01-4400000','Thamel, Kathmandu',NULL,1,'2026-09-24 19:43:42');
/*!40000 ALTER TABLE `restaurants` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `stock_purchases`
--

DROP TABLE IF EXISTS `stock_purchases`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `stock_purchases` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ingredient_id` int(11) NOT NULL,
  `quantity` double NOT NULL,
  `cost_per_unit` double NOT NULL,
  `total_cost` double NOT NULL,
  `supplier_name` varchar(255) DEFAULT NULL,
  `purchased_by` int(11) DEFAULT NULL,
  `purchased_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `ingredient_id` (`ingredient_id`),
  KEY `purchased_by` (`purchased_by`),
  CONSTRAINT `stock_purchases_ibfk_1` FOREIGN KEY (`ingredient_id`) REFERENCES `ingredients` (`id`),
  CONSTRAINT `stock_purchases_ibfk_2` FOREIGN KEY (`purchased_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `stock_purchases`
--

LOCK TABLES `stock_purchases` WRITE;
/*!40000 ALTER TABLE `stock_purchases` DISABLE KEYS */;
/*!40000 ALTER TABLE `stock_purchases` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sync_log`
--

DROP TABLE IF EXISTS `sync_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sync_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `table_name` varchar(255) NOT NULL,
  `record_id` int(11) NOT NULL,
  `action` varchar(255) NOT NULL,
  `data_snapshot` mediumtext DEFAULT NULL,
  `is_synced` tinyint(1) DEFAULT NULL,
  `synced_at` datetime DEFAULT NULL,
  `retry_count` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sync_log`
--

LOCK TABLES `sync_log` WRITE;
/*!40000 ALTER TABLE `sync_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `sync_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `restaurant_id` int(11) DEFAULT NULL,
  `username` varchar(255) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `full_name` varchar(255) NOT NULL,
  `role` varchar(255) NOT NULL,
  `is_active` tinyint(1) DEFAULT NULL,
  `pin` varchar(255) DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `last_seen_at` datetime DEFAULT NULL,
  `session_version` int(11) NOT NULL DEFAULT 0,
  `shift_start` varchar(5) DEFAULT NULL,
  `shift_end` varchar(5) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_per_restaurant` (`username`,`restaurant_id`),
  KEY `restaurant_id` (`restaurant_id`),
  CONSTRAINT `users_ibfk_1` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,NULL,'superadmin','$2b$12$GwY.Xu972b4EVLSx3FKBPOyZdeqcfhXDTPuKlQ2rB2rXlsC9ljI62','Platform Administrator','superadmin',1,NULL,NULL,NULL,0,NULL,NULL,'2026-09-24 19:43:40','2026-09-24 19:43:40'),(2,1,'admin','$2b$12$FLP4yeoXRKlwNQQQEFlE.ePGhLjC.RSo4hlKn8uXSoLNAQU/PC9LG','Administrator','admin',1,'0000',NULL,NULL,0,NULL,NULL,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(3,1,'cashier1','$2b$12$.4MCnUwT3EM27zZNWIBGaOwuSI7OUfMjAKHU2Wcd1ZeUXPAuqD0ba','Sita Cashier','cashier',1,'1111',NULL,NULL,0,NULL,NULL,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(4,1,'waiter1','$2b$12$EjLXcJDMYfSqHGHl9idwh.43ukCngxu.Egiv0MWP.xej3ZoAK91Um','Ram Waiter','waiter',1,'2222',NULL,NULL,0,NULL,NULL,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(5,1,'kitchen1','$2b$12$l6lStl17HvcvFXYwUw83bOVmbAwVyGv2Phg2JEM2w.CTRAZAIm5lO','Hari Kitchen','kitchen',1,'3333',NULL,NULL,0,NULL,NULL,'2026-09-24 19:43:41','2026-09-24 19:43:41'),(6,2,'admin','$2b$12$1.cSlFyT4wL4TnBJxLFJAuqktATn9g8WO4WaGNWuo.QOI0AP4TaL6','Sample Admin','admin',1,'0000',NULL,NULL,0,NULL,NULL,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(7,2,'cashier1','$2b$12$9KNp1tecFOd.ezVnJUheO.wsYO0ZLbxGHCqDSKiG0Lzcvl0L7RH4i','Sita Cashier','cashier',1,'1111',NULL,NULL,0,NULL,NULL,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(8,2,'waiter1','$2b$12$UMOHAdHmGRIpfsjhg0u5RepfwJjZ75FXoxM13RZLl/gilV9/NB3Pu','Ram Waiter','waiter',1,'2222',NULL,NULL,0,NULL,NULL,'2026-09-24 19:43:43','2026-09-24 19:43:43'),(9,2,'kitchen1','$2b$12$iYIIRzLv1q7X/gAwxvdvue5GnELArtgZarnLCm9UjsJJRBkskShfC','Hari Kitchen','kitchen',1,'3333',NULL,NULL,0,NULL,NULL,'2026-09-24 19:43:43','2026-09-24 19:43:43');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed
