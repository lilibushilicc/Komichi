/**
 * Komichi Worker 入口
 * 路由注册与全局中间件
 */
import { Hono } from 'hono';
import type { AppEnv } from './types';
import { corsMiddleware } from './middleware/cors';
import { successResponse, errorResponse } from './utils/response';
import auth from './routes/auth';
import work from './routes/work';
import bookmark from './routes/bookmark';
import r2 from './routes/r2';

const app = new Hono<AppEnv>();

// 全局 CORS（私有化部署，允许所有来源）
app.use('*', corsMiddleware);

// 健康检查
app.get('/ping', (c) =>
  successResponse(c, {
    ping: 'pong',
    service: 'komichi-worker',
    time: new Date().toISOString(),
  }),
);

// 业务路由
app.route('/api/auth', auth);
app.route('/api/work', work);
app.route('/api/bookmark', bookmark);
app.route('/api/r2', r2);

// 根路径信息
app.get('/', (c) =>
  successResponse(c, {
    service: 'komichi-worker',
    version: '1.0.0',
    docs: '/ping',
  }),
);

// 404 兜底
app.notFound((c) => errorResponse(c, '接口不存在', 404, 404));

// 全局错误处理
app.onError((err, c) => {
  console.error('Unhandled error:', err);
  return errorResponse(c, '服务器内部错误', 500, 500, {
    message: err.message,
  });
});

export default app;
