import asyncio
import sys
from typing import Optional
from datetime import datetime, timezone

import cloudscraper
from loguru import logger

# logger init
logger.remove()
logger.add(sys.stdout, format='<g>{time:YYYY-MM-DD HH:mm:ss:SSS}</g> | <c>{level}</c> | <level>{message}</level>')

class ScraperReq:
    def __init__(self, proxy: dict, header: dict):
        self.scraper = cloudscraper.create_scraper(browser={
            'browser': 'chrome',
            'platform': 'windows',
            'mobile': False,
        })
        self.proxy: dict = proxy
        self.header: dict = header

    def post_req(self, url, req_json, req_param):
        # logger.info(self.header)
        # logger.info(req_json)
        return self.scraper.post(url=url, headers=self.header, json=req_json, proxies=self.proxy, params=req_param)

    async def post_async(self, url, req_param=None, req_json=None):
        return await asyncio.to_thread(self.post_req, url, req_json, req_param)

    def get_req(self, url, req_param):
        return self.scraper.get(url=url, headers=self.header, params=req_param, proxies=self.proxy)

    async def get_async(self, url, req_param=None, req_json=None):
        return await asyncio.to_thread(self.get_req, url, req_param)

class NodeGo:
    def __init__(self):
        self.proxy: Optional[str] = ''
        self.token: Optional[str] = ''
        self.wallet_address: Optional[str] = None
        self.last_checkin: Optional[str] = None
        self.reward_point: int = 0
        self.user_scraper: Optional[ScraperReq] = None  # For user-related APIs
        self.node_scraper: Optional[ScraperReq] = None  # For node operations
        self.client_ip: Optional[str] = None
        self.ping_count = 0

    async def init_session(self, proxy, token):
        self.proxy = {'http': proxy, 'https': proxy} if proxy else None
        self.token = token
        
        # Headers for user-related APIs
        user_headers = {
            'Authorization': f'Bearer {token}',
            'Origin': 'https://app.nodego.ai',
            'Referer': 'https://app.nodego.ai/'
        }
        
        # Headers for node operations
        node_headers = {
            'Origin': 'chrome-extension://jbmdcnidiaknboflpljihfnbonjgegah',
            'Referer': 'chrome-extension://jbmdcnidiaknboflpljihfnbonjgegah',
            'Authorization': f'Bearer {token}',
        }
        
        self.user_scraper = ScraperReq(self.proxy, user_headers)
        self.node_scraper = ScraperReq(self.proxy, node_headers)

    async def get_user_info(self):
        try:
            response = await self.user_scraper.get_async('https://nodego.ai/api/user/me')
            data = response.json()
            self.wallet_address = data['metadata'].get('walletAddress')
            last_checkin = data['metadata'].get('lastCheckinAt')
            if last_checkin is None:
                self.last_checkin = 0
            else:
                self.last_checkin = last_checkin

            self.reward_point = data['metadata'].get('rewardPoint', 0)
            logger.info(f"interaction-res: {self.proxy}----ilshAuto----user-info: points:{self.reward_point} last_checkin:{self.last_checkin}")
            return True
        except Exception as e:
            logger.error(f"Failed to get user info: {str(e)}")
            return False

    async def check_in(self):
        try:
            response = await self.user_scraper.post_async('https://nodego.ai/api/user/checkin')
            data = response.json()
            if response.status_code == 201:
                logger.success(f"interaction-res: {self.proxy}----ilshAuto----checkin-success: {data['message']}")
                return True
            else:
                logger.warning(f"interaction-res: {self.proxy}----ilshAuto----checkin-fail: {data['message']}")
                return False
        except Exception as e:
            logger.error(f"Check-in failed: {str(e)}")
            return False

    async def get_client_ip(self):
        try:
            response = await self.node_scraper.get_async('https://api.bigdatacloud.net/data/client-ip')
            self.client_ip = response.json().get('ipString')
            logger.info(f"interaction-res: {self.proxy}----ilshAuto----client-ip: {self.client_ip}")
            return True
        except Exception as e:
            logger.error(f"Failed to get client IP: {str(e)}")
            return False

    async def ping_node(self):
        try:
            payload = {"type": "extension"}
            response = await self.node_scraper.post_async(
                'https://nodego.ai/api/user/nodes/ping',
                req_json=payload
            )
            self.ping_count += 1
            logger.info(f"interaction-res: {self.proxy}----ilshAuto----ping-res: status:{response.status_code} count:{self.ping_count}")
            return True
        except Exception as e:
            logger.error(f"Ping error: {str(e)}")
            return False

async def run(acc: dict):
    node = NodeGo()
    await node.init_session(acc['proxy'], acc['token'])
    
    async def user_tasks():
        """Handle user-related tasks (profile + check-in)"""
        while True:
            try:
                await node.get_user_info()
                
                if node.last_checkin:
                    last_checkin_time = datetime.fromisoformat(node.last_checkin.replace('Z', '+00:00')).astimezone(timezone.utc)
                    current_time = datetime.now(timezone.utc)
                    
                    if (current_time - last_checkin_time).total_seconds() > 86400:
                        await node.check_in()
                
                await asyncio.sleep(1800)
                
            except Exception as e:
                logger.error(f"User task error: {str(e)}")
                await asyncio.sleep(60)

    async def node_tasks():
        """Handle node operations (ping + IP check)"""
        while True:
            try:
                # Execute 3 pings
                for _ in range(3):
                    await node.ping_node()
                    await asyncio.sleep(10)
                
                # Get client IP
                await node.get_client_ip()
                
            except Exception as e:
                logger.error(f"Node task error: {str(e)}, sleeping 2 hours")
                await asyncio.sleep(7200)

    await asyncio.gather(
        user_tasks(),
        node_tasks()
    )

async def main():
    accs = []
    with open('./tokens', 'r', encoding='utf-8') as file:
        for line in file.readlines():
            parts = line.strip().split('----')
            proxy = parts[2]
            token = parts[3]
            acc = {
                'proxy': proxy,
                'token': token
            }
            accs.append(acc)

    tasks = [run(acc) for acc in accs]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    logger.info('🚀 [ILSH] NodeGo v1.0 | Airdrop Campaign Live')
    logger.info('🌐 ILSH Community: t.me/ilsh_auto')
    asyncio.run(main())