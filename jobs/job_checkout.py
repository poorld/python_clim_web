#!/usr/bin/env python
# -*- coding: utf-8 -*-

from jobs import ThreadHandler, OnceJobThread
from common.keywords import get_global_keywords
from common.status import get_global_monitor_status, get_global_batch_order_mode, get_global_test_mode
from service.product_checkout import should_check_products, process_keyword_direct, execute_batch_checkout, reset_batch_round, config
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed


# 策略模式：处理不同的检测模式
class CheckoutStrategy(ABC):
    """检测策略基类"""

    @abstractmethod
    def execute(self, keywords):
        """执行检测策略"""
        pass


class TestModeStrategy(CheckoutStrategy):
    """测试模式策略：根据建单模式设置决定测试行为"""

    def execute(self, keywords):
        from common.status import get_global_batch_order_mode
        batch_mode = get_global_batch_order_mode()

        if batch_mode:
            print("🧪 测试统一建单模式：检测所有款号，合并成一个订单，只弹一次付款")
            self._test_batch_mode(keywords)
        else:
            print("🧪 测试单独建单模式：检测所有款号，每个有货商品立即下单")
            self._test_single_mode(keywords)

    def _test_batch_mode(self, keywords):
        """测试统一建单模式"""
        try:
            # 测试模式：只重置检测轮次，不清空购物车
            from service.product_checkout import state
            with state.batch_lock:
                old_cart_count = len(state.batch_cart_items)
                old_keywords_count = len(state.processed_keywords_batch)

                state.processed_keywords_batch.clear()
                state.batch_round_count = 0
                # 不清空 batch_cart_items，让商品能够累积

                print(f"🔄 [TEST-BATCH] 测试统一建单模式状态重置:")
                print(f"   保留购物车: {old_cart_count} 件商品")
                print(f"   清空关键词记录: {old_keywords_count} → 0")
                print(f"   重置轮次计数: → 0")
            print("🔄 测试统一建单检测开始...")

            # 并发检测所有关键词
            results = self._concurrent_check(keywords)

            # 检查结果
            success_count = sum(1 for result in results.values() if result)
            print(f"📊 测试统一建单检测完成：{success_count}/{len(keywords)} 个关键词有货")

            # 执行批量下单
            self._execute_checkout("测试统一建单")

            print("🎉 测试统一建单模式完成")

        except Exception as e:
            print(f"❌ 测试统一建单模式执行出错: {e}")
            import traceback
            traceback.print_exc()

    def _test_single_mode(self, keywords):
        """测试单独建单模式：每个商品立即下单，不使用购物车"""
        try:
            from service.product_checkout import reset_batch_round, query_product, selectBuyDefect, check_cart, config
            from common.status import set_test_mode

            # 重置状态
            reset_batch_round()
            print("🔄 [TEST-SINGLE] 测试单独建单模式状态重置完成")
            print("🔄 测试单独建单检测开始...")

            # 临时关闭测试模式，让每个商品都能立即下单
            set_test_mode(False)

            # 串行检测所有关键词，每个有货商品立即下单
            success_count = 0
            for i, keyword in enumerate(keywords, 1):
                print(f"🔍 [{i}/{len(keywords)}] 测试关键词: {keyword}")

                try:
                    # 查询商品
                    product = query_product(keyword)
                    if product:
                        print(f"📦 关键词 {keyword} 有库存，准备立即下单")

                        # 加入购物车
                        param_save_cart = selectBuyDefect(product['sku'])
                        if param_save_cart:
                            product_code_value = param_save_cart.get('productCode') or param_save_cart.get('product_code')
                            count = param_save_cart.get('count', 1)

                            if product_code_value:
                                # 立即下单（不等待，不合并）
                                checkout_result = check_cart(product_code_value, count, config.PAY_TYPE_WECHAT)
                                if checkout_result:
                                    success_count += 1
                                    print(f"✅ 关键词 {keyword} 测试成功，已立即下单（第{success_count}个订单）")
                                    # 注意：订单推送已在 checkout 函数中处理，这里不需要重复推送
                                else:
                                    print(f"❌ 关键词 {keyword} 下单失败")
                            else:
                                print(f"❌ 关键词 {keyword} 获取商品代码失败")
                        else:
                            print(f"❌ 关键词 {keyword} 加入购物车失败")
                    else:
                        print(f"📦 关键词 {keyword} 暂无库存")

                except Exception as e:
                    print(f"❌ 处理关键词 {keyword} 时出错: {e}")

            # 恢复测试模式
            set_test_mode(True)

            print(f"📊 测试单独建单检测完成：{success_count}/{len(keywords)} 个关键词有货并已下单")
            print("🎉 测试单独建单模式完成")

        except Exception as e:
            print(f"❌ 测试单独建单模式执行出错: {e}")
            import traceback
            traceback.print_exc()
            # 确保恢复测试模式
            try:
                from common.status import set_test_mode
                set_test_mode(True)
            except:
                pass

    def _concurrent_check(self, keywords):
        """并发检测关键词"""
        print(f"🔄 [CONCURRENT] 开始并发检测 {len(keywords)} 个关键词")
        threads = []
        results = {}

        def worker(keyword):
            try:
                print(f"🔄 [WORKER] 开始处理关键词: {keyword}")
                result = process_keyword_direct(keyword)
                results[keyword] = result
                print(f"✅ [WORKER] 关键词 {keyword} 处理完成，结果: {result}")
            except Exception as e:
                print(f"❌ [WORKER] 处理关键词 {keyword} 时出错: {e}")
                import traceback
                traceback.print_exc()
                results[keyword] = False

        # 创建并启动线程
        for keyword in keywords:
            thread = threading.Thread(target=worker, args=(keyword,))
            thread.daemon = True
            threads.append(thread)
            thread.start()
            print(f"🚀 [CONCURRENT] 启动线程处理关键词: {keyword}")

        # 等待所有线程完成
        print(f"⏳ [CONCURRENT] 等待所有线程完成...")
        for i, thread in enumerate(threads):
            thread.join(timeout=config.THREAD_TIMEOUT)
            print(f"✅ [CONCURRENT] 线程 {i+1}/{len(threads)} 完成")

        print(f"🎉 [CONCURRENT] 所有线程完成，结果: {results}")
        return results

    def _execute_checkout(self, mode_name):
        """执行下单"""
        from service.product_checkout import get_batch_cart_items
        cart_items = get_batch_cart_items()

        # 添加调试信息
        print(f"🔍 {mode_name}模式检查购物车状态:")
        print(f"   购物车商品数量: {len(cart_items) if cart_items else 0}")
        if cart_items:
            for i, item in enumerate(cart_items):
                print(f"   商品{i+1}: {item.get('name', 'Unknown')} (ID: {item.get('cart_id', 'Unknown')})")

        if cart_items:
            print(f"🚀 {mode_name}发现 {len(cart_items)} 件商品，执行{mode_name}下单...")
            execute_batch_checkout()
        else:
            print(f"📦 {mode_name}检测完成，没有发现有货商品")


class BatchModeStrategy(CheckoutStrategy):
    """统一建单模式策略：多轮检测，智能分组"""

    def execute(self, keywords):
        print("🛒 统一建单模式：开始多轮检测...")

        try:
            reset_batch_round()

            max_rounds = config.MAX_DETECTION_ROUNDS
            round_interval = config.ROUND_INTERVAL

            for round_num in range(1, max_rounds + 1):
                print(f"🔄 第 {round_num}/{max_rounds} 轮检测开始...")

                # 并发检测
                results = self._concurrent_check(keywords)

                # 检查结果
                success_count = sum(1 for result in results.values() if result)
                print(f"📊 第 {round_num} 轮检测完成：{success_count}/{len(keywords)} 个关键词有货")

                # 执行批量下单
                self._execute_checkout(f"第 {round_num} 轮")

                # 等待下一轮
                if round_num < max_rounds:
                    print(f"⏰ 等待 {round_interval} 秒后进行下一轮检测...")
                    time.sleep(round_interval)

            print("🎉 多轮检测完成")

        except Exception as e:
            print(f"❌ 多轮检测过程中出错: {e}")
            import traceback
            traceback.print_exc()

    def _concurrent_check(self, keywords):
        """并发检测关键词"""
        threads = []
        results = {}

        def worker(keyword):
            try:
                result = process_keyword_direct(keyword)
                results[keyword] = result
            except Exception as e:
                print(f"❌ 处理关键词 {keyword} 时出错: {e}")
                results[keyword] = False

        # 创建并启动线程
        for keyword in keywords:
            thread = threading.Thread(target=worker, args=(keyword,))
            thread.daemon = True
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join(timeout=config.THREAD_TIMEOUT)

        return results

    def _execute_checkout(self, mode_name):
        """执行下单"""
        from service.product_checkout import get_batch_cart_items
        cart_items = get_batch_cart_items()
        if cart_items:
            print(f"🚀 {mode_name}发现 {len(cart_items)} 件商品，执行批量下单...")
            execute_batch_checkout()


class SingleModeStrategy(CheckoutStrategy):
    """单独建单模式策略：多轮串行检测，立即下单"""

    def execute(self, keywords):
        print("⚡ 单独建单模式：开始多轮检测...")

        try:
            reset_batch_round()

            max_rounds = config.MAX_DETECTION_ROUNDS
            round_interval = config.ROUND_INTERVAL

            for round_num in range(1, max_rounds + 1):
                print(f"🔄 第 {round_num}/{max_rounds} 轮检测开始...")

                success_count = 0
                for keyword in keywords:
                    result = process_keyword_direct(keyword)
                    if result:
                        success_count += 1

                print(f"📊 第 {round_num} 轮检测完成：{success_count}/{len(keywords)} 个关键词有货并下单")

                # 等待下一轮
                if round_num < max_rounds:
                    print(f"⏰ 等待 {round_interval} 秒后进行下一轮检测...")
                    time.sleep(round_interval)

            print("🎉 单独建单多轮检测完成")

        except Exception as e:
            print(f"❌ 单独建单多轮检测出错: {e}")
            import traceback
            traceback.print_exc()


class CheckoutContext:
    """检测上下文：根据模式选择策略"""

    def __init__(self):
        self._strategy = None

    def set_strategy(self, strategy: CheckoutStrategy):
        """设置检测策略"""
        self._strategy = strategy

    def execute_checkout(self, keywords):
        """执行检测"""
        if self._strategy:
            self._strategy.execute(keywords)
        else:
            print("❌ 未设置检测策略")


class RefreshThread(ThreadHandler):
    def __init__(self) -> None:
        super().__init__()
        self.first_run = True

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def handle(self) -> None:
        if get_global_monitor_status() is False:
            return

        # 先检查商品总数是否变化
        if not should_check_products():
            print(f'🔄 {self.__class__.__name__} 商品总数未变化，跳过本次检查')
            return

        keywords = get_global_keywords()
        print(self.__class__, 'handle keywords' + str(keywords))

        # 使用策略模式处理不同的检测模式
        context = CheckoutContext()

        # 根据模式选择策略
        from common.status import get_global_auto_order_status
        test_mode = get_global_test_mode()
        batch_mode = get_global_batch_order_mode()
        auto_order_enabled = get_global_auto_order_status()

        if test_mode:
            context.set_strategy(TestModeStrategy())
        elif not auto_order_enabled:
            # 监控模式：只检测，不下单，不轮询
            context.set_strategy(MonitorOnlyStrategy())
        elif batch_mode:
            context.set_strategy(BatchModeStrategy())
        else:
            context.set_strategy(SingleModeStrategy())

        # 执行检测
        context.execute_checkout(keywords)


class OrderStatusCheckThread(ThreadHandler):
    """订单状态检查线程：定期检查订单付款状态"""

    def __init__(self) -> None:
        super().__init__()
        self.check_interval = 5  # 5秒检查一次

    def startup(self) -> None:
        print("🔍 订单状态检查线程已启动")

    def shutdown(self) -> None:
        print("🔍 订单状态检查线程已停止")

    def handle(self) -> None:
        try:
            from service.product_checkout import check_order_payment_status
            check_order_payment_status()
        except Exception as e:
            print(f"❌ 订单状态检查出错: {e}")

        # 等待指定间隔
        import time
        time.sleep(self.check_interval)

class MonitorOnlyStrategy(CheckoutStrategy):
    """监控模式策略：只检测库存，发送通知，不下单，不轮询"""

    def execute(self, keywords):
        print("📡 监控模式：检测库存变化，只发送通知")

        # 单次检测所有关键词
        results = self._concurrent_check(keywords)

        # 统计结果
        success_count = sum(1 for result in results.values() if result)
        print(f"📊 监控检测完成：{success_count}/{len(keywords)} 个关键词有库存变化")

        if success_count > 0:
            print("📢 已发送库存通知，监控任务完成")
        else:
            print("📊 暂无库存变化")

    def _concurrent_check(self, keywords):
        """并发检测关键词"""
        results = {}

        try:
            # 使用线程池并发检测
            with ThreadPoolExecutor(max_workers=min(len(keywords), 5)) as executor:
                future_to_keyword = {}
                
                # 检查是否可以提交新任务
                for keyword in keywords:
                    try:
                        future = executor.submit(process_keyword_direct, keyword)
                        future_to_keyword[future] = keyword
                    except RuntimeError as e:
                        if 'interpreter shutdown' in str(e):
                            print(f"⚠️ [MONITOR] 解释器正在关闭，停止提交新任务")
                            break
                        else:
                            raise

                for future in as_completed(future_to_keyword):
                    keyword = future_to_keyword[future]
                    try:
                        result = future.result()
                        results[keyword] = result
                        if result:
                            print(f"📢 [MONITOR] 关键词 {keyword} 检测到库存变化")
                        else:
                            print(f"📊 [MONITOR] 关键词 {keyword} 暂无库存变化")
                    except Exception as e:
                        print(f"❌ [MONITOR] 关键词 {keyword} 检测失败: {e}")
                        results[keyword] = False

        except RuntimeError as e:
            if 'interpreter shutdown' in str(e):
                print("⚠️ [MONITOR] 解释器正在关闭，使用串行检测")
                # 降级到串行检测
                for keyword in keywords:
                    try:
                        result = process_keyword_direct(keyword)
                        results[keyword] = result
                    except Exception as e:
                        print(f"❌ [MONITOR] 关键词 {keyword} 检测失败: {e}")
                        results[keyword] = False
            else:
                raise

        return results


# class ProductRefreshThread(ThreadHandler):
#     def __init__(self, keyword) -> None:
#         super().__init__()
#         self._keyword = keyword

#     def startup(self) -> None:
#         pass

#     def shutdown(self) -> None:
#         pass

#     def handle(self) -> None:
#         print(self.__class__, 'handle ' + self._keyword)
#         process_keyword(self._keyword)
