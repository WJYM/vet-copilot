db = db.getSiblingDB('vet-copilot'); // 切换到要创建的数据库

db.createUser({
  user: 'vet-copilot',
  pwd: '123456',
  roles: ["readWrite", "dbAdmin"]
});