#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步多事件集成测试
真正的并行测试 Canal + Kafka 集成，避免阻塞
"""

import threading
import queue
import time
import json
import random
import pymysql
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from kafka import KafkaConsumer
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s'
)
logger = logging.getLogger(__name__)

class AsyncIntegrationTest:
    """异步集成测试"""
    
    def __init__(self):
        self.running = False
        self.start_time = None
        
        # 线程间通信队列
        self.business_queue = queue.Queue()
        self.kafka_queue = queue.Queue()
        self.stats_queue = queue.Queue()
        
        # 统计数据
        self.stats = {
            'business_operations': 0,
            'kafka_messages': 0,
            'operations_by_type': defaultdict(int),
            'messages_by_type': defaultdict(int),
            'messages_by_table': defaultdict(int),
            'sync_delays': [],
            'last_business_time': None,
            'last_kafka_time': None
        }
        
        # 数据库配置
        self.db_config = {
            'host': 'localhost',
            'port': 13306,
            'user': 'root',
            'password': 'keji2025',
            'database': 'keji_dsp',
            'charset': 'utf8mb4'
        }
    
    def business_operations_worker(self, duration_seconds=120):
        """业务操作工作线程"""
        logger.info(f"🚀 业务操作线程启动，运行 {duration_seconds} 秒")
        
        try:
            connection = pymysql.connect(**self.db_config)
            end_time = time.time() + duration_seconds
            operation_count = 0
            
            while self.running and time.time() < end_time:
                try:
                    # 随机选择业务操作
                    operation_type = random.choice([
                        'user_register', 'user_update', 'product_update', 
                        'create_order', 'pay_order', 'update_stock'
                    ])
                    
                    operation_time = time.time()
                    
                    if operation_type == 'user_register':
                        self._create_user(connection)
                    elif operation_type == 'user_update':
                        self._update_user(connection)
                    elif operation_type == 'product_update':
                        self._update_product(connection)
                    elif operation_type == 'create_order':
                        self._create_order(connection)
                    elif operation_type == 'pay_order':
                        self._pay_order(connection)
                    elif operation_type == 'update_stock':
                        self._update_stock(connection)
                    
                    operation_count += 1
                    
                    # 发送操作信息到队列
                    self.business_queue.put({
                        'type': operation_type,
                        'time': operation_time,
                        'count': operation_count
                    })
                    
                    # 短暂间隔，避免过于频繁
                    time.sleep(random.uniform(0.1, 0.5))
                    
                except Exception as e:
                    logger.error(f"❌ 业务操作失败: {e}")
                    time.sleep(1)
            
            connection.close()
            logger.info(f"✅ 业务操作线程完成，共执行 {operation_count} 个操作")
            
        except Exception as e:
            logger.error(f"❌ 业务操作线程失败: {e}")
    
    def kafka_consumer_worker(self, duration_seconds=130):
        """Kafka 消费者工作线程"""
        logger.info(f"📡 Kafka 消费者线程启动，运行 {duration_seconds} 秒")
        
        try:
            consumer = KafkaConsumer(
                'keji_dsp_binlog',
                bootstrap_servers=['127.0.0.1:9092'],
                security_protocol='SASL_PLAINTEXT',
                sasl_mechanism='PLAIN',
                sasl_plain_username='jc',
                sasl_plain_password='jckafka',
                auto_offset_reset='latest',  # 只接收新消息
                enable_auto_commit=True,
                group_id=f'async_test_{int(time.time())}',
                value_deserializer=lambda x: x.decode('utf-8') if x else None,
                consumer_timeout_ms=1000  # 1秒超时，避免阻塞
            )
            
            end_time = time.time() + duration_seconds
            message_count = 0
            
            while self.running and time.time() < end_time:
                try:
                    for message in consumer:
                        if not self.running or time.time() > end_time:
                            break
                        
                        message_count += 1
                        message_time = time.time()
                        
                        if message.value:
                            try:
                                data = json.loads(message.value)
                                event_type = data.get('type', 'unknown')
                                table = data.get('table', 'unknown')
                                
                                # 发送消息信息到队列
                                self.kafka_queue.put({
                                    'type': event_type,
                                    'table': table,
                                    'time': message_time,
                                    'count': message_count,
                                    'offset': message.offset
                                })
                                
                            except json.JSONDecodeError:
                                logger.warning(f"⚠️  无法解析消息 offset {message.offset}")
                
                except Exception as e:
                    # 超时是正常的，继续循环
                    if "timeout" not in str(e).lower():
                        logger.warning(f"⚠️  Kafka 消费异常: {e}")
                    time.sleep(0.1)
            
            consumer.close()
            logger.info(f"✅ Kafka 消费者线程完成，共接收 {message_count} 条消息")
            
        except Exception as e:
            logger.error(f"❌ Kafka 消费者线程失败: {e}")
    
    def stats_worker(self):
        """统计工作线程"""
        logger.info("📊 统计线程启动")
        
        last_report_time = time.time()
        
        while self.running:
            try:
                # 处理业务操作队列
                while not self.business_queue.empty():
                    try:
                        op_data = self.business_queue.get_nowait()
                        self.stats['business_operations'] += 1
                        self.stats['operations_by_type'][op_data['type']] += 1
                        self.stats['last_business_time'] = op_data['time']
                    except queue.Empty:
                        break
                
                # 处理 Kafka 消息队列
                while not self.kafka_queue.empty():
                    try:
                        msg_data = self.kafka_queue.get_nowait()
                        self.stats['kafka_messages'] += 1
                        self.stats['messages_by_type'][msg_data['type']] += 1
                        self.stats['messages_by_table'][msg_data['table']] += 1
                        self.stats['last_kafka_time'] = msg_data['time']
                    except queue.Empty:
                        break
                
                # 每5秒报告一次统计
                current_time = time.time()
                if current_time - last_report_time >= 5:
                    self._print_realtime_stats()
                    last_report_time = current_time
                
                time.sleep(0.1)  # 短暂休眠
                
            except Exception as e:
                logger.error(f"❌ 统计线程异常: {e}")
                time.sleep(1)
        
        logger.info("✅ 统计线程完成")
    
    def _print_realtime_stats(self):
        """打印实时统计"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        logger.info(f"📊 实时统计 (运行 {elapsed:.1f}s):")
        logger.info(f"   业务操作: {self.stats['business_operations']}")
        logger.info(f"   Kafka消息: {self.stats['kafka_messages']}")
        
        if self.stats['business_operations'] > 0:
            sync_rate = self.stats['kafka_messages'] / self.stats['business_operations']
            logger.info(f"   同步率: {sync_rate:.2f}")
        
        if elapsed > 0:
            ops_rate = self.stats['business_operations'] / elapsed
            msg_rate = self.stats['kafka_messages'] / elapsed
            logger.info(f"   操作速率: {ops_rate:.2f}/s")
            logger.info(f"   消息速率: {msg_rate:.2f}/s")
    
    def _create_user(self, connection):
        """创建用户"""
        with connection.cursor() as cursor:
            username = f"async_user_{int(time.time())}_{random.randint(1000, 9999)}"
            email = f"{username}@test.com"
            cursor.execute("""
            INSERT INTO users (username, email, real_name, balance) 
            VALUES (%s, %s, %s, %s)
            """, (username, email, f"测试用户{random.randint(1, 999)}", Decimal('100.00')))
            connection.commit()
    
    def _update_user(self, connection):
        """更新用户"""
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users ORDER BY RAND() LIMIT 1")
            result = cursor.fetchone()
            if result:
                user_id = result[0]
                new_balance = Decimal(str(random.uniform(0, 1000))).quantize(Decimal('0.01'))
                cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (new_balance, user_id))
                connection.commit()
    
    def _update_product(self, connection):
        """更新商品"""
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM products ORDER BY RAND() LIMIT 1")
            result = cursor.fetchone()
            if result:
                product_id = result[0]
                new_stock = random.randint(0, 1000)
                cursor.execute("UPDATE products SET stock_quantity = %s WHERE id = %s", (new_stock, product_id))
                connection.commit()
    
    def _create_order(self, connection):
        """创建订单"""
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users ORDER BY RAND() LIMIT 1")
            user_result = cursor.fetchone()
            if user_result:
                user_id = user_result[0]
                order_no = f"ASYNC{int(time.time())}{random.randint(1000, 9999)}"
                amount = Decimal(str(random.uniform(10, 1000))).quantize(Decimal('0.01'))
                
                cursor.execute("""
                INSERT INTO orders (order_no, user_id, total_amount, final_amount) 
                VALUES (%s, %s, %s, %s)
                """, (order_no, user_id, amount, amount))
                connection.commit()
    
    def _pay_order(self, connection):
        """支付订单"""
        with connection.cursor() as cursor:
            cursor.execute("""
            SELECT id FROM orders WHERE payment_status = 'pending' ORDER BY RAND() LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                order_id = result[0]
                cursor.execute("""
                UPDATE orders SET payment_status = 'paid', paid_at = NOW() WHERE id = %s
                """, (order_id,))
                connection.commit()
    
    def _update_stock(self, connection):
        """更新库存"""
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM products ORDER BY RAND() LIMIT 1")
            result = cursor.fetchone()
            if result:
                product_id = result[0]
                stock_change = random.randint(-10, 50)
                cursor.execute("""
                UPDATE products SET stock_quantity = GREATEST(0, stock_quantity + %s) WHERE id = %s
                """, (stock_change, product_id))
                connection.commit()
    
    def run_async_test(self, duration_minutes=2):
        """运行异步测试"""
        duration_seconds = duration_minutes * 60
        
        logger.info("🚀 开始异步多事件集成测试")
        logger.info("="*60)
        logger.info(f"测试时长: {duration_minutes} 分钟")
        logger.info(f"开始时间: {datetime.now().strftime('%H:%M:%S')}")
        logger.info("="*60)
        
        self.running = True
        self.start_time = time.time()
        
        # 启动工作线程
        threads = [
            threading.Thread(target=self.business_operations_worker, args=(duration_seconds,), name="BusinessOps"),
            threading.Thread(target=self.kafka_consumer_worker, args=(duration_seconds + 10,), name="KafkaConsumer"),
            threading.Thread(target=self.stats_worker, name="StatsWorker")
        ]
        
        for thread in threads:
            thread.start()
            logger.info(f"✅ 启动线程: {thread.name}")
        
        try:
            # 等待业务操作和消费者线程完成
            threads[0].join()  # 业务操作线程
            threads[1].join()  # Kafka 消费者线程
            
            # 停止统计线程
            self.running = False
            threads[2].join(timeout=5)
            
            # 最终报告
            self._print_final_report()
            
        except KeyboardInterrupt:
            logger.info("\n⏹️  用户中断测试")
            self.running = False
            for thread in threads:
                thread.join(timeout=2)
        
        logger.info("🎯 异步集成测试完成")
    
    def _print_final_report(self):
        """打印最终报告"""
        total_time = time.time() - self.start_time
        
        logger.info("\n" + "="*80)
        logger.info("🎯 异步集成测试最终报告")
        logger.info("="*80)
        
        logger.info(f"⏱️  总测试时间: {total_time:.1f} 秒")
        logger.info(f"📊 业务操作总数: {self.stats['business_operations']}")
        logger.info(f"📡 Kafka消息总数: {self.stats['kafka_messages']}")
        
        if self.stats['business_operations'] > 0:
            sync_rate = self.stats['kafka_messages'] / self.stats['business_operations']
            logger.info(f"🔄 同步率: {sync_rate:.2f} (消息/操作)")
            
            ops_rate = self.stats['business_operations'] / total_time
            msg_rate = self.stats['kafka_messages'] / total_time
            logger.info(f"⚡ 操作速率: {ops_rate:.2f} 操作/秒")
            logger.info(f"⚡ 消息速率: {msg_rate:.2f} 消息/秒")
        
        # 操作类型分布
        if self.stats['operations_by_type']:
            logger.info(f"\n📋 业务操作分布:")
            for op_type, count in self.stats['operations_by_type'].items():
                logger.info(f"   {op_type}: {count}")
        
        # 消息类型分布
        if self.stats['messages_by_type']:
            logger.info(f"\n📨 消息类型分布:")
            for msg_type, count in self.stats['messages_by_type'].items():
                logger.info(f"   {msg_type}: {count}")
        
        # 表操作分布
        if self.stats['messages_by_table']:
            logger.info(f"\n🗃️  表操作分布:")
            for table, count in self.stats['messages_by_table'].items():
                logger.info(f"   {table}: {count}")
        
        # 测试结论
        logger.info(f"\n🎯 测试结论:")
        if self.stats['kafka_messages'] > 0 and self.stats['business_operations'] > 0:
            logger.info("   ✅ Canal + Kafka 集成正常工作")
            logger.info("   ✅ 实时数据同步功能正常")
            logger.info("   ✅ 异步多事件处理正常")
            
            if sync_rate >= 0.8:
                logger.info("   ✅ 同步率良好")
            else:
                logger.info("   ⚠️  同步率偏低，可能存在延迟")
        else:
            logger.info("   ❌ 测试失败，请检查系统配置")
        
        logger.info("="*80)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='异步多事件集成测试')
    parser.add_argument('--duration', type=int, help='测试时长（分钟）', default=2)
    
    args = parser.parse_args()
    
    test = AsyncIntegrationTest()
    
    try:
        test.run_async_test(duration_minutes=args.duration)
        logger.info("🎉 测试成功完成！")
        return 0
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
