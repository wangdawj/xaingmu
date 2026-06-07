-- 本地 MySQL 初始化：创建业务用户（Docker 环境由容器自动创建）
CREATE USER IF NOT EXISTS 'energy'@'localhost' IDENTIFIED BY 'energy123';
GRANT ALL PRIVILEGES ON campus_energy.* TO 'energy'@'localhost';
FLUSH PRIVILEGES;
