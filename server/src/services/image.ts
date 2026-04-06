import OpenAI from 'openai';
import {
  generateCacheKey,
  getCachedImage,
  cacheImage,
} from './cache.js';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

interface ImageGenerationParams {
  visualStyle: string;
  locationDescription: string;
  storyContext: string;
}

// Generate image for a scene
export async function generateSceneImage(
  params: ImageGenerationParams
): Promise<string> {
  const { visualStyle, locationDescription, storyContext } = params;

  // Create cache key from all parameters (not just location + style)
  const cacheInput = `${visualStyle}|${locationDescription}|${storyContext}`;
  const cacheKey = generateCacheKey(cacheInput);

  console.log(`\n${'='.repeat(80)}`);
  console.log(`🎨 IMAGE REQUEST`);
  console.log(`⏰ ${new Date().toISOString()}`);
  console.log(`Cache key: ${cacheKey}`);
  console.log('='.repeat(80));

  // Check cache first
  const cachedPath = await getCachedImage(cacheKey);
  if (cachedPath) {
    console.log(`✅ CACHE HIT`);
    console.log(`Path: ${cachedPath}\n`);
    return `/api/media/images/${cacheKey}`;
  }

  console.log(`❌ CACHE MISS - Generating new image`);

  // Generate new image via DALL-E 3
  const prompt = `${visualStyle}. ${locationDescription}. ${storyContext}`;

  console.log(`\n${'='.repeat(80)}`);
  console.log(`🔵 CONNECTING: DALL-E 3`);
  console.log(`⏰ ${new Date().toISOString()}`);
  console.log(`\n--- PROMPT ---`);
  console.log(prompt);
  console.log('='.repeat(80));

  const response = await openai.images.generate({
    model: 'dall-e-3',
    prompt,
    n: 1,
    size: '1024x1024',
    quality: 'standard',
  });

  if (!response.data || response.data.length === 0) {
    throw new Error('No image data returned from DALL-E');
  }

  const imageUrl = response.data[0]?.url;
  if (!imageUrl) {
    throw new Error('No image URL returned from DALL-E');
  }

  console.log(`\n${'='.repeat(80)}`);
  console.log(`🟢 RESPONSE: DALL-E 3`);
  console.log(`⏰ ${new Date().toISOString()}`);
  console.log(`URL: ${imageUrl}`);
  console.log(`Downloading and caching...`);
  console.log('='.repeat(80));

  // Download image
  const imageResponse = await fetch(imageUrl);
  if (!imageResponse.ok) {
    throw new Error(`Failed to download image: ${imageResponse.statusText}`);
  }

  const imageBuffer = Buffer.from(await imageResponse.arrayBuffer());

  // Cache the image
  await cacheImage(cacheKey, imageBuffer);

  console.log(`✅ IMAGE CACHED AND READY`);
  console.log(`🔴 DISCONNECT: DALL-E 3\n`);

  return `/api/media/images/${cacheKey}`;
}
