#!/usr/bin/env python
# -*- coding: utf-8 -*-

from . import ThreadHandler, OnceJobThread
from ..common.keywords import get_global_keywords
from ..common.status import get_global_monitor_status, get_global_batch_order_mode, get_global_test_mode
from ..service.product_checkout import should_check_products, process_keyword_direct, execute_batch_checkout, reset_batch_round, config
from ..service.product_checkout import query_product, selectBuyDefect, _handle_notification_mode, _build_product_info, submit_batch_order
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..common.logger import get_logger

logger = get_logger()

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
        from ..common.status import get_global_batch_order_mode
        batch_mode = get_global_batch_order_mode()

        if batch_mode:
            logger.info("🧪 测试统一建单模式：检测所有款号，合并成一个订单，只弹一次付款")
            self._test_batch_mode(keywords)
        else:
            logger.info("🧪 测试单独建单模式：检测所有款号，每个有货商品立即下单")
            self._test_single_mode(keywords)

    def _test_batch_mode(self, keywords):
        """测试统一建单模式"""
        try:
            # 测试模式：只重置检测轮次，不清空购物车
            from ..service.product_checkout import state
            with state.batch_lock:
                old_cart_count = len(state.batch_cart_items)
                old_keywords_count = len(state.processed_keywords_batch)

                state.processed_keywords_batch.clear()
                state.batch_round_count = 0
                # 不清空 batch_cart_items，让商品能够累积

                logger.info(f"🔄 [TEST-BATCH] 测试统一建单模式状态重置:")
                logger.info(f"   保留购物车: {old_cart_count} 件商品")
                logger.info(f"   清空关键词记录: {old_keywords_count} → 0")
                logger.info(f"   重置轮次计数: → 0")
            logger.info("🔄 测试统一建单检测开始...")

            # 并发检测所有关键词
            results = self._concurrent_check(keywords)

            # 检查结果
            success_count = sum(1 for result in results.values() if result)
            logger.info(f"📊 测试统一建单检测完成：{success_count}/{len(keywords)} 个关键词有货")

            # 执行批量下单
            self._execute_checkout("测试统一建单")

            logger.info("🎉 测试统一建单模式完成")

        except Exception as e:
            logger.error(f"❌ 测试统一建单模式执行出错: {e}", exc_info=True)

    def _test_single_mode(self, keywords):
        """测试单独建单模式：每个商品加入购物车立即下单"""
        try:
            from ..service.product_checkout import reset_batch_round, query_product, selectBuyDefect, check_cart, config
            from ..common.status import set_test_mode

            # 重置状态
            reset_batch_round()
            logger.info("🔄 [TEST-SINGLE] 测试单独建单模式状态重置完成")
            logger.info("🔄 测试单独建单检测开始...")

            # 临时关闭测试模式，让每个商品都能立即下单
            set_test_mode(False)

            # 串行检测所有关键词，每个有货商品立即下单
            success_count = 0
            for i, keyword in enumerate(keywords, 1):
                logger.info(f"🔍 [{i}/{len(keywords)}] 测试关键词: {keyword}")

                try:
                    # 查询商品
                    product = query_product(keyword)
                    if product:
                        logger.info(f"📦 关键词 {keyword} 有库存，准备立即下单")

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
                                    logger.info(f"✅ 关键词 {keyword} 测试成功，已立即下单（第{success_count}个订单）")
                                    # 注意：订单推送已在 checkout 函数中处理，这里不需要重复推送
                                else:
                                    logger.error(f"❌ 关键词 {keyword} 下单失败")
                            else:
                                logger.error(f"❌ 关键词 {keyword} 获取商品代码失败")
                        else:
                            logger.error(f"❌ 关键词 {keyword} 加入购物车失败")
                    else:
                        logger.info(f"📦 关键词 {keyword} 暂无库存")

                except Exception as e:
                    logger.error(f"❌ 处理关键词 {keyword} 时出错: {e}", exc_info=True)

            # 恢复测试模式
            set_test_mode(True)

            logger.info(f"📊 测试单独建单检测完成：{success_count}/{len(keywords)} 个关键词有货并已下单")
            logger.info("🎉 测试单独建单模式完成")

        except Exception as e:
            logger.error(f"❌ 测试单独建单模式执行出错: {e}", exc_info=True)
            # 确保恢复测试模式
            try:
                from ..common.status import set_test_mode
                set_test_mode(True)
            except:
                pass

    def _concurrent_check(self, keywords):
        """并发检测关键词"""
        logger.info(f"🔄 [CONCURRENT] 开始并发检测 {len(keywords)} 个关键词")
        threads = []
        results = {}

        def worker(keyword):
            try:
                logger.info(f"🔄 [WORKER] 开始处理关键词: {keyword}")
                result = process_keyword_direct(keyword)
                results[keyword] = result
                logger.info(f"✅ [WORKER] 关键词 {keyword} 处理完成，结果: {result}")
            except Exception as e:
                logger.error(f"❌ [WORKER] 处理关键词 {keyword} 时出错: {e}", exc_info=True)
                results[keyword] = False

        # 创建并启动线程
        for keyword in keywords:
            thread = threading.Thread(target=worker, args=(keyword,))
            thread.daemon = True
            threads.append(thread)
            thread.start()
            logger.info(f"🚀 [CONCURRENT] 启动线程处理关键词: {keyword}")

        # 等待所有线程完成
        logger.info(f"⏳ [CONCURRENT] 等待所有线程完成...")
        for i, thread in enumerate(threads):
            thread.join(timeout=config.THREAD_TIMEOUT)
            logger.info(f"✅ [CONCURRENT] 线程 {i+1}/{len(threads)} 完成")

        logger.info(f"🎉 [CONCURRENT] 所有线程完成，结果: {results}")
        return results

    def _execute_checkout(self, mode_name):
        """执行下单"""
        from ..service.product_checkout import get_batch_cart_items
        cart_items = get_batch_cart_items()

        # 添加调试信息
        logger.info(f"🔍 {mode_name}模式检查购物车状态:")
        logger.info(f"   购物车商品数量: {len(cart_items) if cart_items else 0}")
        if cart_items:
            for i, item in enumerate(cart_items):
                logger.info(f"   商品{i+1}: {item.get('name', 'Unknown')} (ID: {item.get('cart_id', 'Unknown')})")

        if cart_items:
            logger.info(f"🚀 {mode_name}发现 {len(cart_items)} 件商品，执行{mode_name}下单...")
            execute_batch_checkout()
        else:
            logger.info(f"📦 {mode_name}检测完成，没有发现有货商品")


class BatchModeStrategy(CheckoutStrategy):
    """统一建单模式策略：单次检测，智能分组"""

    def execute(self, keywords):
        from ..common.status import get_global_group_enabled, get_global_group_size

        group_enabled = get_global_group_enabled()

        if group_enabled:
            logger.info("🛒 统一建单模式：启用分组执行...")
            self._execute_with_groups(keywords)
        else:
            logger.info("🛒 统一建单模式：传统执行...")
            self._execute_traditional(keywords)

    def _execute_traditional(self, keywords):
        """传统执行方式：所有关键词一起处理"""
        try:
            reset_batch_round()

            # 并发检测所有关键词
            results = self._concurrent_check(keywords)

            # 检查结果
            success_count = sum(1 for result in results.values() if result)
            logger.info(f"📊 统一建单检测完成：{success_count}/{len(keywords)} 个关键词有货")

            # 执行批量下单
            self._execute_checkout("统一建单")

            logger.info("🎉 统一建单检测完成")

        except Exception as e:
            logger.error(f"❌ 统一建单检测出错: {e}", exc_info=True)

    def _execute_with_groups(self, keywords):
        """分组执行方式：按组并行处理"""
        try:
            from ..common.status import get_global_group_size
            from concurrent.futures import ThreadPoolExecutor, as_completed

            group_size = get_global_group_size()
            groups = self._create_keyword_groups(keywords, group_size)

            logger.info(f"📦 关键词分组完成：{len(keywords)}个关键词分为{len(groups)}组，每组{group_size}个")

            # 并行执行各组
            with ThreadPoolExecutor(max_workers=min(len(groups), 5)) as executor:
                futures = {
                    executor.submit(self._process_group, group_id, group_keywords): group_id
                    for group_id, group_keywords in groups.items()
                }

                total_success = 0
                for future in as_completed(futures):
                    group_id = futures[future]
                    try:
                        success_count = future.result()
                        total_success += success_count
                        logger.info(f"✅ [组{group_id}] 处理完成")
                    except Exception as e:
                        logger.error(f"❌ [组{group_id}] 处理失败: {e}")

            logger.info(f"🎉 分组执行完成：总计{total_success}个关键词有货并下单")

        except Exception as e:
            logger.error(f"❌ 分组执行出错: {e}", exc_info=True)

    def _create_keyword_groups(self, keywords, group_size):
        """将关键词按指定大小分组"""
        groups = {}
        for i in range(0, len(keywords), group_size):
            group_id = i // group_size + 1
            groups[group_id] = keywords[i:i + group_size]
        return groups

    def _process_group(self, group_id, keywords):
        """处理单个分组 - 使用独立购物车避免线程竞争"""
        logger.info(f"🔄 [组{group_id}] 开始检测: {', '.join(keywords)}")

        try:
            # 为本组创建独立的购物车
            group_cart = []

            # 并发检测本组关键词，直接收集到组购物车
            results = self._concurrent_check_with_cart(keywords, group_cart)

            # 检查结果
            success_count = sum(1 for result in results.values() if result)
            logger.info(f"📊 [组{group_id}] 检测完成：{success_count}/{len(keywords)} 个关键词有货")

            # 使用组独立购物车执行下单
            if success_count > 0:
                self._execute_group_checkout(group_id, group_cart)
            else:
                logger.info(f"📦 [组{group_id}] 无货商品，跳过下单")

            return success_count

        except Exception as e:
            logger.error(f"❌ [组{group_id}] 处理出错: {e}")
            return 0

    def _concurrent_check_with_cart(self, keywords, group_cart):
        """并发检测关键词并收集到指定购物车"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = {}

        with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_THREADS) as executor:
            futures = {
                executor.submit(self._process_keyword_to_cart, keyword, group_cart): keyword
                for keyword in keywords
            }

            for future in as_completed(futures):
                keyword = futures[future]
                try:
                    result = future.result()
                    results[keyword] = result
                except Exception as e:
                    logger.error(f"❌ 关键词 {keyword} 检测失败: {e}")
                    results[keyword] = False

        return results

    def _process_keyword_to_cart(self, keyword, group_cart):
        """处理单个关键词并添加到指定购物车"""
        try:
            # 查询商品
            product = query_product(keyword)
            if not product:
                logger.debug(f"📡 关键词 {keyword} 暂无库存")
                return False

            # 获取系统状态
            from ..common.status import get_global_auto_order_status, get_global_test_mode, get_global_batch_order_mode
            auto_order_enabled = get_global_auto_order_status()
            test_mode = get_global_test_mode()
            batch_mode = get_global_batch_order_mode()

            # 纯监控模式
            if not auto_order_enabled and not test_mode:
                return _handle_notification_mode(keyword, product)

            # 下单模式
            return self._handle_group_order_mode(keyword, product, test_mode, batch_mode, group_cart)

        except Exception as e:
            logger.error(f"❌ 处理关键词 {keyword} 时出错: {e}")
            return False

    def _handle_group_order_mode(self, keyword, product, test_mode, batch_mode, group_cart):
        """处理分组下单模式"""
        param_save_cart = selectBuyDefect(product['sku'])

        if not param_save_cart:
            logger.error(f"❌ [PROCESS] 关键词 {keyword} selectBuyDefect 失败")
            return True

        product_code_value = param_save_cart.get('productCode') or param_save_cart.get('product_code')
        count = param_save_cart.get('count', 1)

        # 构建商品信息
        product_info = _build_product_info(keyword, product_code_value, product)

        # 直接添加到组购物车（避免全局状态竞争）
        cart_item = {
            'keyword': keyword,
            'name': product_info['name'],
            'price': product_info['price'],
            'count': count,
            'product_code': product_code_value,
            'cart_id': param_save_cart.get('cart_id', f"group_cart_{keyword}")
        }

        group_cart.append(cart_item)
        logger.info(f"✅ [组购物车] 关键字 {keyword} 商品已加入组购物车")

        return True

    def _execute_group_checkout(self, group_id, group_cart):
        """执行分组下单"""
        if not group_cart:
            logger.info(f"📦 [组{group_id}] 购物车为空，无需下单")
            return

        logger.info(f"🛒 [组{group_id}] 开始下单，共 {len(group_cart)} 件商品")

        # 简化逻辑：直接将购物车商品作为一个订单
        order = {
            'items': group_cart,
            'total_count': sum(int(item['count']) for item in group_cart),
            'total_amount': sum(float(item['price']) * int(item['count']) for item in group_cart),
            'product_count': len(group_cart)
        }

        logger.info(f"🛒 [组{group_id}] 订单详情: {order['product_count']}种商品, {order['total_count']}件, ¥{order['total_amount']:.2f}")

        # 执行订单
        try:
            logger.info(f"🚀 [组{group_id}] 开始处理订单...")

            # 构建多商品URL
            cart_ids = [item['cart_id'] for item in order['items']]
            checked_params = "&".join([f"checked={cart_id}" for cart_id in cart_ids])
            settle_url = f"https://fenxiao.clim.cn/shop/settle.do?{checked_params}"

            logger.info(f"🔗 [组{group_id}] 结算链接: {settle_url}")

            # 执行下单
            order_code = submit_batch_order(settle_url, order)

            if order_code:
                logger.info(f"✅ [组{group_id}] 订单下单成功，订单号: {order_code}")

                # 立即推送订单号（这样可以立即弹窗）
                try:
                    logger.info(f"🔍 [组{group_id}] 开始立即推送订单号: {order_code}")
                    from ..service.web import push_order_to_clients

                    push_order_to_clients(order_code)
                    logger.info(f"🚀 [组{group_id}] 订单号推送成功: {order_code}")

                except Exception as e:
                    logger.error(f"❌ [组{group_id}] 推送订单失败: {e}", exc_info=True)

            else:
                logger.error(f"❌ [组{group_id}] 订单下单失败")

        except Exception as e:
            logger.error(f"❌ [组{group_id}] 处理订单时出错: {e}", exc_info=True)



    def _concurrent_check(self, keywords):
        """并发检测关键词"""
        threads = []
        results = {}

        def worker(keyword):
            try:
                result = process_keyword_direct(keyword)
                results[keyword] = result
            except Exception as e:
                logger.error(f"❌ 处理关键词 {keyword} 时出错: {e}", exc_info=True)
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
        from ..service.product_checkout import get_batch_cart_items
        cart_items = get_batch_cart_items()
        if cart_items:
            logger.info(f"🚀 {mode_name}发现 {len(cart_items)} 件商品，执行批量下单...")
            execute_batch_checkout()


class SingleModeStrategy(CheckoutStrategy):
    """单独建单模式策略：单次检测，立即下单"""

    def execute(self, keywords):
        logger.info("⚡ 单独建单模式：开始检测...")

        try:
            reset_batch_round()

            success_count = 0
            for keyword in keywords:
                result = process_keyword_direct(keyword)
                if result:
                    success_count += 1

            logger.info(f"📊 单独建单检测完成：{success_count}/{len(keywords)} 个关键词有货并下单")
            logger.info("🎉 单独建单检测完成")

        except Exception as e:
            logger.error(f"❌ 单独建单检测出错: {e}", exc_info=True)


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
            logger.error("❌ 未设置检测策略")


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
            logger.info(f'🔄 {self.__class__.__name__} 商品总数未变化，跳过本次检查')
            return

        keywords = get_global_keywords()
        logger.debug(f'{self.__class__.__name__} handle keywords: {keywords}')

        # 使用策略模式处理不同的检测模式
        context = CheckoutContext()

        # 根据模式选择策略
        from ..common.status import get_global_auto_order_status
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
        logger.info("🔍 订单状态检查线程已启动")

    def shutdown(self) -> None:
        logger.info("🔍 订单状态检查线程已停止")

    def handle(self) -> None:
        try:
            from ..service.product_checkout import check_order_payment_status
            check_order_payment_status()
        except Exception as e:
            logger.error(f"❌ 订单状态检查出错: {e}", exc_info=True)

        # 等待指定间隔
        import time
        time.sleep(self.check_interval)

class MonitorOnlyStrategy(CheckoutStrategy):
    """监控模式策略：只检测库存，发送通知，不下单，不轮询"""

    def execute(self, keywords):
        logger.info("📡 监控模式：检测库存变化，只发送通知")

        # 单次检测所有关键词
        results = self._concurrent_check(keywords)

        # 统计结果
        success_count = sum(1 for result in results.values() if result)
        logger.info(f"📊 监控检测完成：{success_count}/{len(keywords)} 个关键词有库存变化")

        if success_count > 0:
            logger.info("📢 已发送库存通知，监控任务完成")
        else:
            logger.info("📊 暂无库存变化")

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
                            logger.warning(f"⚠️ [MONITOR] 解释器正在关闭，停止提交新任务")
                            break
                        else:
                            raise

                for future in as_completed(future_to_keyword):
                    keyword = future_to_keyword[future]
                    try:
                        result = future.result()
                        results[keyword] = result
                        if result:
                            logger.info(f"📢 [MONITOR] 关键词 {keyword} 检测到库存变化")
                        else:
                            logger.debug(f"📊 [MONITOR] 关键词 {keyword} 暂无库存变化")
                    except Exception as e:
                        logger.error(f"❌ [MONITOR] 关键词 {keyword} 检测失败: {e}", exc_info=True)
                        results[keyword] = False

        except RuntimeError as e:
            if 'interpreter shutdown' in str(e):
                logger.warning("⚠️ [MONITOR] 解释器正在关闭，使用串行检测")
                # 降级到串行检测
                for keyword in keywords:
                    try:
                        result = process_keyword_direct(keyword)
                        results[keyword] = result
                    except Exception as e:
                        logger.error(f"❌ [MONITOR] 关键词 {keyword} 检测失败: {e}", exc_info=True)
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
#         logger.debug(f'{self.__class__.__name__} handle {self._keyword}')
#         process_keyword(self._keyword)
