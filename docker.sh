
docker run -d --name milvus-standalone -p 19530:19530 -p 9091:9091 -v /home/zh/milvus-data:/var/lib/milvus milvusdb/milvus:latest