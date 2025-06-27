const { app } = require('@azure/functions');
const { ComputerVisionClient } = require('@azure/cognitiveservices-computervision');
const { CognitiveServicesCredentials } = require('@azure/ms-rest-azure-js');

// Azure Computer Vision 클라이언트 설정
const visionKey = process.env.AZURE_COMPUTER_VISION_KEY;
const visionEndpoint = process.env.AZURE_COMPUTER_VISION_ENDPOINT;

// 환경변수 검증
if (!visionKey || !visionEndpoint) {
    console.error('❌ Computer Vision 환경변수가 설정되지 않았습니다.');
    console.error('필요한 환경변수: AZURE_COMPUTER_VISION_KEY, AZURE_COMPUTER_VISION_ENDPOINT');
}

const credentials = new CognitiveServicesCredentials(visionKey);
const visionClient = new ComputerVisionClient(credentials, visionEndpoint);

// Storage 클라이언트는 필요할 때만 초기화
let blobServiceClient = null;

function initializeBlobServiceClient() {
    if (!blobServiceClient) {
        const { BlobServiceClient } = require('@azure/storage-blob');
        const storageConnectionString = process.env.AZURE_STORAGE_CONNECTION_STRING;
        
        if (!storageConnectionString) {
            throw new Error('AZURE_STORAGE_CONNECTION_STRING 환경변수가 설정되지 않았습니다.');
        }
        
        console.log('🔗 Storage 클라이언트 초기화 중...');
        blobServiceClient = BlobServiceClient.fromConnectionString(storageConnectionString);
    }
    return blobServiceClient;
}

// 제품 카테고리 키워드 정의
const categoryKeywords = {
  fragile: [
    'glass', 'ceramic', 'porcelain', 'crystal', 'mirror', 'vase', 'bottle',
    'wine glass', 'cup', 'mug', 'plate', 'bowl', 'glassware', 'china',
    'figurine', 'ornament', 'lamp', 'bulb', 'screen', 'monitor', 'tv',
    '유리', '도자기', '거울', '꽃병', '컵', '접시', '그릇', '화면', '모니터'
  ],
  electronics: [
    'computer', 'laptop', 'phone', 'smartphone', 'tablet', 'camera',
    'television', 'monitor', 'keyboard', 'mouse', 'speaker', 'headphone',
    'watch', 'smartwatch', 'router', 'modem', 'printer', 'scanner',
    'console', 'gaming', 'drone', 'remote', 'charger', 'cable',
    'processor', 'motherboard', 'hard drive', 'memory', 'graphics card',
    '컴퓨터', '노트북', '휴대폰', '스마트폰', '태블릿', '카메라', '텔레비전',
    '키보드', '마우스', '스피커', '헤드폰', '시계', '프린터', '게임기'
  ],
  clothing: [
    'shirt', 'pants', 'dress', 'jacket', 'coat', 'sweater', 'hoodie',
    'jeans', 'shorts', 'skirt', 'blouse', 'top', 'suit', 'tie',
    'shoes', 'boots', 'sneakers', 'sandals', 'hat', 'cap', 'scarf',
    'gloves', 'socks', 'underwear', 'bra', 'swimwear', 'pajamas',
    '셔츠', '바지', '드레스', '재킷', '코트', '스웨터', '후드티',
    '청바지', '반바지', '치마', '신발', '부츠', '운동화', '모자', '스카프'
  ],
  food: [
    'apple', 'banana', 'orange', 'bread', 'milk', 'cheese', 'meat',
    'chicken', 'fish', 'vegetables', 'fruit', 'rice', 'pasta',
    'pizza', 'burger', 'sandwich', 'cake', 'cookie', 'chocolate',
    'coffee', 'tea', 'water', 'juice', 'soda', 'beer', 'wine',
    'cereal', 'snack', 'candy', 'yogurt', 'egg', 'butter',
    '사과', '바나나', '오렌지', '빵', '우유', '치즈', '고기',
    '닭고기', '생선', '야채', '과일', '쌀', '파스타', '피자', '케이크'
  ]
};

// 제품 분류 함수
function classifyProduct(tags, objects, description) {
  const allText = [
    ...tags.map(tag => tag.name.toLowerCase()),
    ...objects.map(obj => obj.object.toLowerCase()),
    description.toLowerCase()
  ].join(' ');

  const scores = {
    fragile: 0,
    electronics: 0,
    clothing: 0,
    food: 0
  };

  // 키워드 매칭으로 점수 계산
  for (const [category, keywords] of Object.entries(categoryKeywords)) {
    keywords.forEach(keyword => {
      if (allText.includes(keyword.toLowerCase())) {
        scores[category] += 1;
      }
    });
  }

  // 태그 신뢰도 가중치 적용
  tags.forEach(tag => {
    const confidence = tag.confidence;
    for (const [category, keywords] of Object.entries(categoryKeywords)) {
      if (keywords.some(keyword => tag.name.toLowerCase().includes(keyword.toLowerCase()))) {
        scores[category] += confidence;
      }
    }
  });

  // 최고 점수 카테고리 반환
  const maxCategory = Object.keys(scores).reduce((a, b) => 
    scores[a] > scores[b] ? a : b
  );

  return {
    category: maxCategory,
    confidence: scores[maxCategory],
    scores: scores
  };
}

// 깨지기 쉬운 정도 평가
function assessFragility(category, tags, objects) {
  let fragilityLevel = 'low';
  let fragilityScore = 0;

  // 카테고리별 기본 점수
  const categoryFragility = {
    fragile: 0.8,
    electronics: 0.6,
    clothing: 0.1,
    food: 0.3
  };

  fragilityScore = categoryFragility[category] || 0;

  // 특정 키워드로 추가 점수
  const highFragilityKeywords = ['glass', 'ceramic', 'crystal', 'mirror', 'screen', '유리', '도자기', '거울', '화면'];
  const mediumFragilityKeywords = ['plastic', 'metal', 'electronic', '플라스틱', '금속', '전자'];

  const allItems = [...tags.map(t => t.name.toLowerCase()), ...objects.map(o => o.object.toLowerCase())];

  allItems.forEach(item => {
    if (highFragilityKeywords.some(keyword => item.includes(keyword.toLowerCase()))) {
      fragilityScore += 0.3;
    } else if (mediumFragilityKeywords.some(keyword => item.includes(keyword.toLowerCase()))) {
      fragilityScore += 0.1;
    }
  });

  // 점수에 따른 레벨 결정
  if (fragilityScore >= 0.7) {
    fragilityLevel = 'high';
  } else if (fragilityScore >= 0.4) {
    fragilityLevel = 'medium';
  }

  return {
    level: fragilityLevel,
    score: Math.min(fragilityScore, 1.0)
  };
}

// 포장 권장사항 함수
function getPackagingRecommendations(category, fragilityLevel) {
  const recommendations = {
    fragile: {
      high: {
        materials: ['에어캡', '스티로폼', '골판지', '충격방지재'],
        instructions: '매우 조심스럽게 포장. 충격 방지재 사용 필수. 여러 겹 포장 권장.',
        shippingNotes: '깨지기 쉬움 라벨 부착, 이 면을 위로 라벨, 던지지 마시오',
        handlingCode: 'FRAGILE_HIGH'
      },
      medium: {
        materials: ['에어캡', '신문지', '골판지'],
        instructions: '적절한 충격 방지재 사용. 안전한 포장.',
        shippingNotes: '주의 취급 라벨 부착',
        handlingCode: 'FRAGILE_MEDIUM'
      },
      low: {
        materials: ['골판지', '신문지'],
        instructions: '기본적인 보호 포장.',
        shippingNotes: '일반 취급 가능',
        handlingCode: 'FRAGILE_LOW'
      }
    },
    electronics: {
      high: {
        materials: ['정전기 방지재', '에어캡', '충격 방지재', '습기제거제'],
        instructions: '정전기 및 충격 방지 필수. 습기 차단 포장.',
        shippingNotes: '전자제품 라벨, 습기 주의, 정전기 주의',
        handlingCode: 'ELECTRONICS_HIGH'
      },
      medium: {
        materials: ['에어캡', '골판지', '습기제거제'],
        instructions: '충격 방지 포장. 습기 차단.',
        shippingNotes: '전자제품 라벨, 습기 주의',
        handlingCode: 'ELECTRONICS_MEDIUM'
      },
      low: {
        materials: ['골판지', '포장재'],
        instructions: '기본 포장.',
        shippingNotes: '전자제품',
        handlingCode: 'ELECTRONICS_LOW'
      }
    },
    clothing: {
      high: {
        materials: ['진공포장', '비닐포장', '골판지'],
        instructions: '습기 방지 포장. 압축 포장 가능.',
        shippingNotes: '의류 라벨, 습기 주의',
        handlingCode: 'CLOTHING_HIGH'
      },
      medium: {
        materials: ['비닐포장', '골판지'],
        instructions: '기본 포장. 습기 방지.',
        shippingNotes: '의류',
        handlingCode: 'CLOTHING_MEDIUM'
      },
      low: {
        materials: ['포장지'],
        instructions: '간단 포장.',
        shippingNotes: '일반 취급',
        handlingCode: 'CLOTHING_LOW'
      }
    },
    food: {
      high: {
        materials: ['보냉재', '단열재', '밀폐용기', '습기제거제'],
        instructions: '온도 및 습도 관리 필수. 신선도 유지 포장.',
        shippingNotes: '식품 라벨, 유통기한 확인, 냉장보관',
        handlingCode: 'FOOD_HIGH'
      },
      medium: {
        materials: ['밀폐용기', '포장재', '습기제거제'],
        instructions: '습기 방지 포장. 온도 관리.',
        shippingNotes: '식품 라벨, 유통기한 확인',
        handlingCode: 'FOOD_MEDIUM'
      },
      low: {
        materials: ['포장재'],
        instructions: '기본 포장.',
        shippingNotes: '식품',
        handlingCode: 'FOOD_LOW'
      }
    }
  };

  return recommendations[category]?.[fragilityLevel] || {
    materials: ['기본 포장재'],
    instructions: '기본 포장 방법 적용.',
    shippingNotes: '일반 취급',
    handlingCode: 'GENERAL'
  };
}

// Azure Blob Storage에서 이미지 버퍼 가져오기
async function getImageBufferFromBlob(containerName, blobName) {
  try {
    const blobClient = initializeBlobServiceClient();
    const containerClient = blobClient.getContainerClient(containerName);
    const blobClientFile = containerClient.getBlobClient(blobName);
    
    // Blob 존재 여부 확인
    const exists = await blobClientFile.exists();
    if (!exists) {
      throw new Error(`Blob ${blobName}이 컨테이너 ${containerName}에 존재하지 않습니다.`);
    }
    
    // Blob을 Buffer로 다운로드 (Computer Vision API 호환성을 위해)
    const downloadResponse = await blobClientFile.downloadToBuffer();
    return downloadResponse;
  } catch (error) {
    throw new Error(`Blob 읽기 실패: ${error.message}`);
  }
}

// 유틸리티 함수들
function getCategoryKorean(category) {
  const categoryMap = {
    fragile: '깨지기 쉬운 제품',
    electronics: '전자제품',
    clothing: '의류',
    food: '식품'
  };
  return categoryMap[category] || category;
}

function getFragilityKorean(level) {
  const levelMap = {
    high: '높음',
    medium: '보통',
    low: '낮음'
  };
  return levelMap[level] || level;
}

// 메인 Azure Function
app.http('analyzeProduct', {
  methods: ['POST'],
  authLevel: 'function',
  route: 'analyze-product',
  handler: async (request, context) => {
    const startTime = Date.now();
    context.log('🚀 제품 분석 요청 시작');
    
    try {
      // 환경변수 검증
      if (!visionKey || !visionEndpoint) {
        throw new Error('Computer Vision 환경변수가 설정되지 않았습니다.');
      }
      
      // 요청 본문 파싱
      const requestBody = await request.json();
      const { containerName, blobName, imageUrl } = requestBody;
      
      context.log('📝 요청 데이터:', { containerName, blobName, imageUrl: imageUrl ? 'URL 제공됨' : '없음' });
      
      let analysis;
      
      if (containerName && blobName) {
        // Azure Blob Storage에서 이미지 분석
        context.log(`📦 Blob 분석 시작: ${containerName}/${blobName}`);
        
        const imageBuffer = await getImageBufferFromBlob(containerName, blobName);
        
        analysis = await visionClient.analyzeImageInStream(imageBuffer, {
          visualFeatures: ['Tags', 'Objects', 'Description', 'Categories'],
          details: ['Landmarks'],
          language: 'en'
        });
        
      } else if (imageUrl) {
        // URL에서 이미지 분석
        context.log(`🌐 URL 분석 시작: ${imageUrl}`);
        
        analysis = await visionClient.analyzeImage(imageUrl, {
          visualFeatures: ['Tags', 'Objects', 'Description', 'Categories'],
          details: ['Landmarks'],
          language: 'en'
        });
        
      } else {
        return {
          status: 400,
          jsonBody: {
            error: 'containerName과 blobName 또는 imageUrl이 필요합니다.',
            example: {
              blob: { containerName: 'products', blobName: 'image.jpg' },
              url: { imageUrl: 'https://example.com/image.jpg' }
            }
          }
        };
      }
      
      // 분석 결과 처리
      const tags = analysis.tags || [];
      const objects = analysis.objects || [];
      const description = analysis.description?.captions?.[0]?.text || '';
      
      context.log(`✅ 분석 완료 - Tags: ${tags.length}, Objects: ${objects.length}`);
      
      // 제품 분류
      const classification = classifyProduct(tags, objects, description);
      context.log(`🏷️ 분류 결과: ${classification.category} (신뢰도: ${classification.confidence.toFixed(2)})`);
      
      // 깨지기 쉬운 정도 평가
      const fragility = assessFragility(classification.category, tags, objects);
      context.log(`💥 깨지기 쉬운 정도: ${fragility.level} (점수: ${fragility.score.toFixed(2)})`);
      
      // 포장 권장사항
      const packagingRecommendations = getPackagingRecommendations(
        classification.category,
        fragility.level
      );
      
      // 처리 시간 계산
      const processingTime = Date.now() - startTime;
      
      // 추가 메타데이터
      const metadata = {
        processedAt: new Date().toISOString(),
        processingTime: `${processingTime}ms`,
        source: containerName ? 'blob' : 'url',
        sourceDetails: containerName ? `${containerName}/${blobName}` : imageUrl,
        visionApiVersion: '3.2'
      };
      
      // 최종 결과
      const result = {
        classification: {
          category: classification.category,
          categoryKorean: getCategoryKorean(classification.category),
          confidence: Math.round(classification.confidence * 100) / 100,
          allScores: Object.fromEntries(
            Object.entries(classification.scores).map(([k, v]) => [k, Math.round(v * 100) / 100])
          )
        },
        fragility: {
          level: fragility.level,
          levelKorean: getFragilityKorean(fragility.level),
          score: Math.round(fragility.score * 100) / 100
        },
        packaging: packagingRecommendations,
        analysis: {
          tags: tags.slice(0, 10).map(tag => ({
            name: tag.name,
            confidence: Math.round(tag.confidence * 100) / 100
          })),
          objects: objects.slice(0, 5).map(obj => ({
            object: obj.object,
            confidence: Math.round(obj.confidence * 100) / 100,
            rectangle: obj.rectangle
          })),
          description: description,
          categories: analysis.categories?.slice(0, 3).map(cat => ({
            name: cat.name,
            score: Math.round(cat.score * 100) / 100
          })) || []
        },
        metadata: metadata
      };
      
      context.log(`🎉 분석 성공적으로 완료 (처리시간: ${processingTime}ms)`);
      
      return {
        status: 200,
        headers: {
          'Content-Type': 'application/json; charset=utf-8'
        },
        jsonBody: result
      };
      
    } catch (error) {
      // ✅ 올바른 오류 로깅 방식 (Azure Functions v4)
      context.error('❌ 분석 중 오류 발생:', error.message);
      console.error('📊 상세 오류 정보:', {
        message: error.message,
        stack: error.stack,
        timestamp: new Date().toISOString()
      });
      
      return {
        status: 500,
        jsonBody: {
          error: '이미지 분석 중 오류가 발생했습니다.',
          message: error.message,
          timestamp: new Date().toISOString(),
          suggestion: '환경변수 설정과 이미지 URL/Blob을 확인해주세요.'
        }
      };
    }
  }
});

// 헬스체크 Function
app.http('healthCheck', {
  methods: ['GET'],
  authLevel: 'anonymous',
  route: 'health',
  handler: async (request, context) => {
    const envCheck = {
      visionKey: !!process.env.AZURE_COMPUTER_VISION_KEY,
      visionEndpoint: !!process.env.AZURE_COMPUTER_VISION_ENDPOINT,
      storageConnection: !!process.env.AZURE_STORAGE_CONNECTION_STRING
    };
    
    return {
      status: 200,
      jsonBody: {
        status: 'healthy',
        service: 'Azure Computer Vision 제품 분류 서비스',
        version: '2.0.0',
        timestamp: new Date().toISOString(),
        environment: process.env.AZURE_FUNCTIONS_ENVIRONMENT || 'development',
        environmentVariables: envCheck
      }
    };
  }
});

// 서비스 정보 Function
app.http('serviceInfo', {
  methods: ['GET'],
  authLevel: 'anonymous',
  route: 'info',
  handler: async (request, context) => {
    return {
      status: 200,
      jsonBody: {
        service: 'Azure Computer Vision 제품 분류 서비스',
        version: '2.0.0',
        description: '제품 이미지를 분석하여 카테고리 분류 및 깨지기 쉬운 정도를 판단하는 서비스',
        categories: {
          fragile: '깨지기 쉬운 제품',
          electronics: '전자제품',
          clothing: '의류',
          food: '식품'
        },
        fragilityLevels: {
          high: '높음',
          medium: '보통',
          low: '낮음'
        },
        endpoints: [
          'POST /api/analyze-product - 제품 이미지 분석',
          'GET /api/health - 서비스 상태 확인',
          'GET /api/info - 서비스 정보'
        ],
        inputFormats: {
          blob: {
            containerName: 'string (Azure Blob Storage 컨테이너 이름)',
            blobName: 'string (Blob 파일 이름)'
          },
          url: {
            imageUrl: 'string (이미지 URL)'
          }
        },
        sampleRequests: [
          {
            type: 'URL 분석',
            method: 'POST',
            endpoint: '/api/analyze-product',
            body: {
              imageUrl: 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=400'
            }
          },
          {
            type: 'Blob 분석',
            method: 'POST', 
            endpoint: '/api/analyze-product',
            body: {
              containerName: 'products',
              blobName: 'smartphone.jpg'
            }
          }
        ]
      }
    };
  }
});