from django.db import models
import boto3
from datetime import datetime

class InventoryItem(models.Model):
    item_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField()
    quantity = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100)
    supplier = models.CharField(max_length=200)
    warehouse_location = models.CharField(max_length=200)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    image_url = models.URLField(null=True, blank=True)
    
    class Meta:
        ordering = ['-last_updated']
        indexes = [
            models.Index(fields=['item_id']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.item_id})"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Sync to DynamoDB
        self.sync_to_dynamodb()
    
    def sync_to_dynamodb(self):
        """Sync inventory item to AWS DynamoDB"""
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('InventoryItems')
        
        table.put_item(
            Item={
                'item_id': self.item_id,
                'name': self.name,
                'quantity': self.quantity,
                'price': str(self.price),
                'category': self.category,
                'last_updated': datetime.now().isoformat()
            }
        )
    
    def upload_image_to_s3(self, image_file):
        """Upload product image to S3"""
        s3 = boto3.client('s3')
        bucket_name = 'inventory-images'
        key = f"products/{self.item_id}/{image_file.name}"
        
        s3.upload_fileobj(image_file, bucket_name, key)
        self.image_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
        self.save()

class StockAlert(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=50)
    threshold = models.IntegerField()
    triggered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def check_and_trigger(self):
        """Check stock levels and trigger Lambda function if needed"""
        if self.item.quantity <= self.threshold and not self.triggered:
            self.trigger_lambda_alert()
            self.triggered = True
            self.save()
    
    def trigger_lambda_alert(self):
        """Trigger AWS Lambda function for stock alerts"""
        lambda_client = boto3.client('lambda')
        payload = {
            'item_id': self.item.item_id,
            'item_name': self.item.name,
            'current_quantity': self.item.quantity,
            'threshold': self.threshold
        }
        
        lambda_client.invoke(
            FunctionName='StockAlertFunction',
            InvocationType='Event',
            Payload=str(payload)
        )
