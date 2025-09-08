"""create tables

Revision ID: 7c0af1a2fb85
Revises: 1263dbd3bcff
Create Date: 2025-08-29 14:40:39.472159
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c0af1a2fb85'
down_revision: Union[str, Sequence[str], None] = '1263dbd3bcff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=16), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('company_name', sa.String(), nullable=False),
        sa.Column('company_information_page_files', sa.JSON(), server_default='[]', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('phone_number', sa.String(), nullable=False),
        sa.Column('country', sa.String(), nullable=False),
        sa.Column('timezone', sa.String(), nullable=False),
        sa.Column('subscription_plan', sa.String(), server_default='free', nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('role', sa.String(), server_default='customer', nullable=False),
        sa.Column('permissions', sa.ARRAY(sa.String()), server_default=sa.text("ARRAY['read']"), nullable=False),
        sa.Column('otp_code', sa.String(), nullable=True),
        sa.Column('otp_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('otp_attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('otp_expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('otp_created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('access_token', sa.String(), nullable=True),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('trial_start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_expiry_date', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_customer_id'),
        sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=True)

    # Company info
    op.create_table(
        'company_information_page_details',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=16), nullable=False),
        sa.Column('company_name', sa.String(), nullable=False),
        sa.Column('business_reg_number', sa.String(), nullable=False),
        sa.Column('industry_type', sa.String(), nullable=False),
        sa.Column('other_industry', sa.String(), nullable=True),
        sa.Column('num_employees', sa.Integer(), nullable=True),
        sa.Column('company_website', sa.String(), nullable=True),
        sa.Column('business_phone', sa.String(), nullable=False),
        sa.Column('business_email', sa.String(), nullable=False),
        sa.Column('address_street', sa.String(), nullable=False),
        sa.Column('address_city', sa.String(), nullable=False),
        sa.Column('address_state', sa.String(), nullable=False),
        sa.Column('address_postcode', sa.String(), nullable=False),
        sa.Column('address_country', sa.String(), nullable=False),
        sa.Column('company_logo_path', sa.String(), nullable=True),
        sa.Column('registration_doc_path', sa.String(), nullable=False),
        sa.Column('additional_files_paths', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('terms_accepted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_company_information_page_details_id'), 'company_information_page_details', ['id'], unique=False)

    # Documents
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=16), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_id'), 'documents', ['id'], unique=False)
    op.create_index(op.f('ix_documents_user_id'), 'documents', ['user_id'], unique=False)

    # Subscriptions
    op.create_table(
        'subscriptions',
        sa.Column('subscription_id', sa.String(length=16), nullable=False),
        sa.Column('subscriptions_plan', sa.String(), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('auto_renew', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('trial_used', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('projects_used', sa.Integer(), server_default='0', nullable=False),
        sa.Column('documents_uploaded', sa.Integer(), server_default='0', nullable=False),
        sa.Column('queries_made', sa.Integer(), server_default='0', nullable=False),
        sa.Column('features_enabled', sa.ARRAY(sa.String()), nullable=True),
        sa.ForeignKeyConstraint(['subscription_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('subscription_id')
    )

    # Document chunks
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('vector_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_id'), 'document_chunks', ['id'], unique=False)
    op.create_index(op.f('ix_document_chunks_vector_id'), 'document_chunks', ['vector_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_document_chunks_vector_id'), table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_id'), table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_document_id'), table_name='document_chunks')
    op.drop_table('document_chunks')

    op.drop_table('subscriptions')

    op.drop_index(op.f('ix_documents_user_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_id'), table_name='documents')
    op.drop_table('documents')

    op.drop_index(op.f('ix_company_information_page_details_id'), table_name='company_information_page_details')
    op.drop_table('company_information_page_details')

    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
