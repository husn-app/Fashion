"""add ip_and_user_agent

Revision ID: 58cb4f88af8f
Revises: f0c1ab6000a0
Create Date: 2024-10-22 01:31:23.920408

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '58cb4f88af8f'
down_revision = 'f0c1ab6000a0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_click', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ip', sa.String(length=45), nullable=True))
        batch_op.add_column(sa.Column('user_agent', sa.String(length=255), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_click', schema=None) as batch_op:
        batch_op.drop_column('user_agent')
        batch_op.drop_column('ip')

    # ### end Alembic commands ###
